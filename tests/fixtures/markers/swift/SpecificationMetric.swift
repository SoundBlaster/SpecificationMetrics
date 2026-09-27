protocol SpecificationMetricV1 {}

struct DirectResponseSpec: SpecificationMetricV1 {
    func accepts(_ value: Int) -> Bool {
        value > 0
    }
}

struct ExtendedResponseSpec {}

extension ExtendedResponseSpec: SpecificationMetricV1 {}
