struct _TypedRule;

impl Specification<bool> for _TypedRule {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}

fn accepts(_rule: &_TypedRule) {}
