pub trait SpecificationMetricV1 {}

pub trait Specification<T> {}

pub struct MarkedResponseSpec;

impl SpecificationMetricV1 for MarkedResponseSpec {}

impl Specification<bool> for MarkedResponseSpec {}

#[repr(i32)]
pub enum AlternateResponseSpec {
    Accepted = if cfg!(unix) { 1 } else { 0 },
    Rejected = 2,
}

impl self::SpecificationMetricV1 for self::AlternateResponseSpec {}

pub struct QualifiedResponseSpec;

impl self::SpecificationMetricV1 for self::QualifiedResponseSpec {}

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
