//! Provider-neutral categorical packets and an explicitly invoked Codex adapter.
mod codex;
mod contract;
#[cfg(unix)]
mod process;

pub use codex::{ExecutionReport, argv as codex_argv, execute, load_prepared};
pub use contract::{
    Backend, BackendConfig, CategoricalPacket, CategoricalTask, ChoiceQuestion, Effort,
    PreparedTask, prepare, read_json,
};

pub fn prepare_files(
    packet: &std::path::Path,
    config: &std::path::Path,
) -> anyhow::Result<PreparedTask> {
    let packet = read_json(&contract::bounded_file(packet, contract::INPUT_LIMIT)?)?;
    let config = contract::bounded_file(config, 8192)?;
    prepare(packet, toml::from_str(std::str::from_utf8(&config)?)?)
}
