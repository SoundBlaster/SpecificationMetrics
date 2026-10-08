use rust_jev::{rust_decision::*, *};
use serde::Deserialize;
use serde_json::json;
use std::{
    collections::HashSet,
    io::Write,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Item {
    candidate_id: String,
    axis: String,
    state: String,
    instructions: String,
    criteria: Vec<(String, String)>,
}

fn validate(items: &[Item]) -> Result<(), &'static str> {
    if items.is_empty() || items.len() > 16 {
        return Err("Expected 1..16 requests");
    }
    let mut seen = HashSet::new();
    for item in items {
        if !["opportunity", "concern_kind"].contains(&item.axis.as_str())
            || item.candidate_id.is_empty()
            || !seen.insert((&item.candidate_id, &item.axis))
            || item.state.len() > 24 * 1024
            || item.instructions.len() > 2048
            || !(2..=4).contains(&item.criteria.len())
            || serde_json::from_str::<serde_json::Value>(&item.state).is_err()
        {
            return Err("Invalid or duplicate bounded request");
        }
        let mut ids = HashSet::new();
        if item
            .criteria
            .iter()
            .any(|(id, desc)| id.is_empty() || desc.is_empty() || !ids.insert(id))
        {
            return Err("Invalid criteria");
        }
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 2 || !["--validate", "--live"].contains(&args[0].as_str()) {
        return Err("Usage: specmetrics-jev-eval --validate|--live INPUT.json; --live authorizes up to 16 billable requests".into());
    }
    let items: Vec<Item> = serde_json::from_slice(&std::fs::read(&args[1])?)?;
    validate(&items)?;
    if args[0] == "--validate" {
        println!("Validated {} requests; no inference", items.len());
        return Ok(());
    }
    let key = std::env::var("COREINFRA_API_KEY").map_err(|_| "Missing COREINFRA_API_KEY")?;
    let mut config = Config::new(&key, "jev-latest")?;
    config.endpoint = std::env::var("JEV_ENDPOINT").map_err(|_| "Missing explicit JEV_ENDPOINT")?;
    config.provider_label = "coreinfra-evaluation".into();
    config.timeout = Duration::from_secs(30);
    config.connect_timeout = Duration::from_secs(10);
    config.state_encoding = StateEncoding::Json;
    let mut client = JevClient::new(config)?;
    let mut total_tokens = 0;
    for item in items {
        let request = Request {
            question_id: item.axis.clone(),
            context: item.state,
            instructions: item.instructions,
            options: item
                .criteria
                .into_iter()
                .map(|(id, description)| Choice {
                    value: id.clone(),
                    id,
                    description,
                })
                .collect(),
        };
        let start = std::time::Instant::now();
        let report = client.decide(&request, &Policy::default(), Observation::default);
        let accepted = match &report.core.decision {
            Decision::Accepted(label) => Some(label.clone()),
            _ => None,
        };
        let operational_failure = matches!(
            &report.core.decision,
            Decision::Failed(_) | Decision::Cancelled
        );
        let evidence = match report.prediction {
            Some(JevPrediction::Choice(p)) => {
                json!({"selected_id":p.selected_id,"probabilities":p.probabilities,"confidence":format!("{:?}",p.confidence)})
            }
            _ => serde_json::Value::Null,
        };
        let metadata = report.metadata.map(|m| {
            if let Some(u) = &m.usage { total_tokens += u.input_tokens.unwrap_or(0) + u.output_tokens.unwrap_or(0); }
            json!({"provider":m.provider_label,"requested_model":m.requested_model,"returned_model":m.returned_model,
                "request_id":m.typesafe_request_id,"gateway_request_id":m.gateway_request_id,
                "usage":m.usage.map(|u|json!({"input_tokens":u.input_tokens,"output_tokens":u.output_tokens}))})
        });
        println!(
            "{}",
            json!({"candidate_id":item.candidate_id,"axis":item.axis,"accepted_label":accepted,
            "decision":format!("{:?}",report.core.decision),"invocations":report.core.invocations,"rules":report.core.rules.len(),
            "evidence":evidence,"adapter_error":report.adapter_error.map(|e|e.to_string()),"metadata":metadata,
            "elapsed_seconds":start.elapsed().as_secs_f64(),"received_unix_seconds":SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs()})
        );
        std::io::stdout().flush()?;
        if operational_failure {
            return Err("Stopped after operational failure; no retries".into());
        }
        if total_tokens > 40_000 {
            return Err("Stopped at observed token budget; no retries".into());
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn item() -> Item {
        Item {
            candidate_id: "x".into(),
            axis: "opportunity".into(),
            state: "{}".into(),
            instructions: "classify".into(),
            criteria: vec![("a".into(), "A".into()), ("b".into(), "B".into())],
        }
    }
    #[test]
    fn bounds_and_duplicates_are_rejected_before_inference() {
        assert!(validate(&[item()]).is_ok());
        assert!(validate(&[]).is_err());
        assert!(validate(&(0..17).map(|_| item()).collect::<Vec<_>>()).is_err());
        assert!(validate(&[item(), item()]).is_err());
        let mut invalid = item();
        invalid.state = "not JSON".into();
        assert!(validate(&[invalid]).is_err());
        let mut invalid = item();
        invalid.criteria.push(("a".into(), "duplicate".into()));
        assert!(validate(&[invalid]).is_err());
    }
}
