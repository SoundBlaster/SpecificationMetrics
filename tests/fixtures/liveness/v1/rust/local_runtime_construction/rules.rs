struct _LocalRule;

impl Specification<bool> for _LocalRule {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}

fn run() {
    let rule = _LocalRule;
    evaluate(rule);
}
