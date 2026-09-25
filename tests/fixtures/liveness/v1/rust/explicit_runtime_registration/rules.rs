struct _RegisteredRule;

impl Specification<bool> for _RegisteredRule {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
