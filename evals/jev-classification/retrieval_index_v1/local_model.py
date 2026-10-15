"""Lazy, offline-only adapter for the existing pinned EmbeddingGemma experiment."""
import hashlib
import importlib.metadata
from pathlib import Path

from embeddinggemma_pilot_v1 import MODEL, REVISION
from .source import digest, encoded


def model_identity(path):
    path = Path(path)
    if path.name != REVISION or not (path / 'config.json').is_file():
        raise ValueError('expected the existing pinned local model snapshot')
    inventory = []
    for item in sorted(p for p in path.rglob('*') if p.is_file()):
        sha = hashlib.sha256()
        with item.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(block)
        inventory.append((str(item.relative_to(path)), sha.hexdigest()))
    return digest(encoded(inventory))


class LocalEncoder:
    def __init__(self, path, device='mps'):
        self.path, self.device, self.model = Path(path), device, None
        self.profile = dict(model=MODEL, revision=REVISION, dimensions=768, document_prompt='',
                            normalize=True, model_files_sha256=model_identity(self.path),
                            runtime={name: importlib.metadata.version(name) for name in
                                     ('torch', 'transformers', 'sentence-transformers')},
                            device=device, dtype='float32', adapter='specmetrics.local-embedding/v1',
                            truncation='reject')

    def __call__(self, texts):
        if self.model is None:
            import torch
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(str(self.path), device=self.device, local_files_only=True,
                                            trust_remote_code=False,
                                            config_kwargs={'vision_config': None, 'audio_config': None},
                                            model_kwargs={'torch_dtype': torch.float32})
            if self.model.get_embedding_dimension() != self.profile['dimensions']:
                raise ValueError('model dimension differs')
        if any(len(self.model.tokenizer.encode(text)) > self.model.max_seq_length for text in texts):
            raise ValueError('input exceeds model context; refusing silent truncation')
        return self.model.encode(texts, prompt='', normalize_embeddings=True, batch_size=4,
                                 show_progress_bar=False).tolist()
