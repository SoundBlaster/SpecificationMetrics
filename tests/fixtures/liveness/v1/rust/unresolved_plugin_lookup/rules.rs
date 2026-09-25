struct _ConfiguredRule;

impl Specification<bool> for _ConfiguredRule {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
