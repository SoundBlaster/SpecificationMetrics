struct Ready;

impl Specification<bool> for Ready {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
