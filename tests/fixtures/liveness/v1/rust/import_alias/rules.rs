struct _AliasedRule;

impl Specification<bool> for _AliasedRule {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
