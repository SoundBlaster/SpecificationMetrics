fn call_unrelated_paths() {
    other_crate::rules::Ready::new();
    self::rules::Ready::new();
}
