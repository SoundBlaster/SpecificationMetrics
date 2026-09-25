struct _Ready;

impl Specification<bool> for _Ready {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
