impl Specification<bool> for crate::models::Ready {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
