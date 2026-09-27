mod rules {
    struct _InlineRule;

    impl Specification<bool> for _InlineRule {
        fn is_satisfied_by(&self, value: &bool) -> bool {
            *value
        }
    }

    fn run() {
        let rule = _InlineRule;
        evaluate(rule);
    }
}
