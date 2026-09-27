pub trait SpecificationMetricV1 {}

pub trait Specification<T> {}

pub struct MarkedResponseSpec;

impl SpecificationMetricV1 for MarkedResponseSpec {}

impl Specification<bool> for MarkedResponseSpec {}

pub enum AlternateResponseSpec {
    Accepted,
    Rejected,
}

impl crate::SpecificationMetricV1 for AlternateResponseSpec {}

impl MarkedResponseSpec {
    pub fn accepts(value: bool) -> bool {
        if value { true } else { false }
    }
}

impl AlternateResponseSpec {
    pub fn accepts(value: bool) -> bool {
        match value {
            true => true,
            false => false,
        }
    }
}

pub fn unrelated_decision(value: bool) -> bool {
    match value {
        true => true,
        false => false,
    }
}
