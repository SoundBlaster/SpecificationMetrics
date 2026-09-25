struct _Unused;

impl Specification<bool> for _Unused {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
