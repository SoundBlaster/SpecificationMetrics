import { createHash } from 'node:crypto';
import { cache } from 'promptfoo';

const DEFAULT_ENDPOINT = 'https://api.typesafe.ai/v1/systemone';
const MAX_RESPONSE_BYTES = 1024 * 1024;

async function readBoundedText(response) {
  const declaredLength = Number(response.headers.get('content-length'));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_RESPONSE_BYTES) {
    throw new Error('response too large');
  }
  if (!response.body) {
    return '';
  }

  const reader = response.body.getReader();
  const chunks = [];
  let totalBytes = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    totalBytes += value.byteLength;
    if (totalBytes > MAX_RESPONSE_BYTES) {
      await reader.cancel();
      throw new Error('response too large');
    }
    chunks.push(value);
  }

  const bytes = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(bytes);
}

export default class JevProvider {
  constructor(options = {}) {
    this.providerId = options.id || 'typesafe-jev-custom';
    this.config = options.config || {};
  }

  id() {
    return this.providerId;
  }

  async callApi(prompt) {
    const apiKey = process.env.TYPESAFE_API_KEY;
    if (!apiKey) {
      return { error: 'TYPESAFE_API_KEY is required for the opt-in Jev evaluation' };
    }

    let state;
    try {
      state = JSON.parse(prompt);
    } catch {
      return { error: 'Rendered Jev state must be a JSON object or array' };
    }
    if (state === null || typeof state !== 'object') {
      return { error: 'Rendered Jev state must be a JSON object or array' };
    }

    const endpoint = this.config.endpoint || DEFAULT_ENDPOINT;
    const requestBody = JSON.stringify({
      model: this.config.model || 'jev-1.13.0', state, questions: this.config.questions,
    });
    // Partition by credentials without storing them in the cache key/value.
    const key = cache.getScopedCacheKey('jev-validated-v1:' + createHash('sha256')
      .update(JSON.stringify([endpoint, apiKey, requestBody])).digest('hex'));
    const enabled = cache.isCacheEnabled();
    if (enabled) {
      const stored = await cache.getCache().get(key);
      if (stored) {
        try {
          const result = JSON.parse(stored);
          return { ...result, cached: true,
            tokenUsage: result.tokenUsage && { ...result.tokenUsage, cached: result.tokenUsage.total },
            metadata: { typesafe: { ...result.metadata.typesafe, responseSource: 'cache' } } };
        } catch { /* A corrupt cache entry is a miss, never a provider response. */ }
      }
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.config.timeoutMs ?? 30_000);
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        redirect: 'error',
        signal: controller.signal,
        headers: {
          authorization: `Bearer ${apiKey}`,
          'content-type': 'application/json',
        },
        body: requestBody,
      });

      let bodyText;
      try {
        bodyText = await readBoundedText(response);
      } catch {
        return { error: 'TypeSafe Jev response exceeded 1 MiB' };
      }
      if (!response.ok) {
        return { error: `TypeSafe Jev returned HTTP ${response.status}` };
      }

      let body;
      try {
        body = JSON.parse(bodyText);
      } catch {
        return { error: 'TypeSafe Jev returned malformed JSON' };
      }
      if (!body || typeof body.model !== 'string' || !body.answers || typeof body.answers !== 'object') {
        return { error: 'TypeSafe Jev response is missing model or answers' };
      }

      const result = {
        cached: false,
        output: body.answers,
        tokenUsage: body.usage && {
          prompt: body.usage.input_tokens ?? 0,
          completion: body.usage.output_tokens ?? 0,
          total: (body.usage.input_tokens ?? 0) + (body.usage.output_tokens ?? 0),
        },
        metadata: {
          typesafe: {
            requestedModel: this.config.model || 'jev-1.13.0',
            returnedModel: body.model,
            usage: body.usage || null,
            responseSource: 'live',
          },
        },
      };
      if (enabled) await cache.getCache().set(key, JSON.stringify(result));
      return result;
    } catch (error) {
      const reason = error?.name === 'AbortError' ? 'request timed out' : 'request failed';
      return { error: `TypeSafe Jev ${reason}` };
    } finally {
      clearTimeout(timeout);
    }
  }
}
