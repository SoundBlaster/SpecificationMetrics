pub struct PublishedRule;

impl Specification<bool> for PublishedRule {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
