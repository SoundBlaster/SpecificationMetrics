use anyhow::Result;
use std::{
    io::{Read, Write},
    os::unix::process::CommandExt,
    path::Path,
    process::{Child, Command, Stdio},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};

pub(super) struct Capture {
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub diagnostic: Option<&'static str>,
}

pub(super) struct ProcessLimits<'a> {
    pub timeout: Duration,
    pub bytes: usize,
    pub authentication_home: &'a Path,
}

struct Guard(Child);
impl Drop for Guard {
    fn drop(&mut self) {
        // The child starts a new process group. Kill its descendants too before
        // joining pipe readers, including when the direct child already exited.
        unsafe {
            libc::kill(-(self.0.id() as i32), libc::SIGKILL);
        }
        let _ = self.0.wait();
    }
}

pub(super) fn capture(
    executable: &Path,
    args: &[String],
    input: &[u8],
    cwd: &Path,
    limits: ProcessLimits<'_>,
    response_file: Option<&Path>,
) -> Result<Capture> {
    let ProcessLimits {
        timeout,
        bytes: limit,
        authentication_home,
    } = limits;
    let mut command = Command::new(executable);
    command
        .args(args)
        .current_dir(cwd)
        .env_clear()
        .process_group(0)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    // Authentication stays owned by Codex; no environment values enter artifacts.
    for name in [
        "PATH",
        "HOME",
        "USER",
        "CODEX_API_KEY",
        "OPENAI_API_KEY",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    ] {
        if let Some(value) = std::env::var_os(name) {
            command.env(name, value);
        }
    }
    command.env("CODEX_HOME", authentication_home);
    let mut child = Guard(command.spawn()?);
    let mut stdin = child.0.stdin.take().unwrap();
    let input = input.to_vec();
    let writer = thread::spawn(move || stdin.write_all(&input));
    let exceeded = Arc::new(AtomicBool::new(false));
    fn reader<R: Read + Send + 'static>(
        pipe: R,
        limit: usize,
        flag: Arc<AtomicBool>,
    ) -> thread::JoinHandle<std::io::Result<Vec<u8>>> {
        thread::spawn(move || {
            let mut bytes = Vec::new();
            pipe.take(limit as u64 + 1).read_to_end(&mut bytes)?;
            if bytes.len() > limit {
                flag.store(true, Ordering::Relaxed);
            }
            Ok(bytes)
        })
    }
    let stdout = reader(child.0.stdout.take().unwrap(), limit, exceeded.clone());
    let stderr = reader(child.0.stderr.take().unwrap(), limit, exceeded.clone());
    let started = Instant::now();
    let mut diagnostic = loop {
        if exceeded.load(Ordering::Relaxed)
            || response_file
                .is_some_and(|path| std::fs::metadata(path).is_ok_and(|m| m.len() > limit as u64))
        {
            break Some("output_limit");
        }
        if started.elapsed() >= timeout {
            break Some("timeout");
        }
        match child.0.try_wait() {
            Ok(Some(status)) => {
                break if status.success() {
                    None
                } else {
                    Some("process_failed")
                };
            }
            Ok(None) => thread::sleep(Duration::from_millis(10)),
            Err(_) => break Some("process_failed"),
        }
    };
    drop(child);
    let wrote = writer.join().ok().and_then(Result::ok).is_some();
    let out = stdout.join().ok().and_then(Result::ok);
    let err = stderr.join().ok().and_then(Result::ok);
    if exceeded.load(Ordering::Relaxed) {
        diagnostic = Some("output_limit");
    }
    if diagnostic.is_none() && (!wrote || out.is_none() || err.is_none()) {
        diagnostic = Some("process_io_failed");
    }
    Ok(Capture {
        stdout: out.unwrap_or_default(),
        stderr: err.unwrap_or_default(),
        diagnostic,
    })
}
