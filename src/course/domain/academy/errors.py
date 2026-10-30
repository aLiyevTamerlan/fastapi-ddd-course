from typing import Final


class AcademyErrorCodes:
    # Academy
    INVALID_ACADEMY: Final = "invalid_academy"
    INVALID_ACADEMY_NAME: Final = "invalid_academy_name"
    INVALID_CONTACT_EMAIL: Final = "invalid_contact_email"
    INVALID_ACADEMY_STATUS: Final = "invalid_academy_status"
    INVALID_REJECTION_REASON: Final = "invalid_rejection_reason"
    ACADEMY_NOT_FOUND: Final = "academy_not_found"
    ACADEMY_NOT_ACTIVE: Final = "academy_not_active"
    ACADEMY_NOT_PENDING_VERIFICATION: Final = "academy_not_pending_verification"
    ACADEMY_NOT_SUSPENDED: Final = "academy_not_suspended"
    ACADEMY_SUSPENDED: Final = "academy_suspended"
    ACADEMY_ALREADY_SUSPENDED: Final = "academy_already_suspended"
    ACADEMY_ALREADY_ACTIVE: Final = "academy_already_active"
    ACADEMY_ALREADY_VERIFIED: Final = "academy_already_verified"
    ACADEMY_NOT_VERIFIED: Final = "academy_not_verified"
    ACADEMY_NAME_TAKEN: Final = "academy_name_taken"
    CONTACT_EMAIL_TAKEN: Final = "contact_email_taken"

    # Course
    INVALID_COURSE: Final = "invalid_course"
    INVALID_COURSE_TITLE: Final = "invalid_course_title"
    INVALID_DATE_RANGE: Final = "invalid_date_range"
    INVALID_PRICE: Final = "invalid_price"
    INVALID_CURRENCY: Final = "invalid_currency"
    INVALID_CAPACITY: Final = "invalid_capacity"


class CourseErrorCodes:
    """Stable, machine-readable codes for Course domain failures.

    The string is what the API returns to the client (error `detail.code`);
    `base_controller` maps the DomainError's *type* (validation/conflict/...) to
    the HTTP status, never these codes. Keep the strings stable — the frontend
    switches on them.
    """

    # --- title ---
    TITLE_EMPTY:             Final[str] = "course.title_empty"
    TITLE_TOO_LONG:          Final[str] = "course.title_too_long"

    # --- description ---
    DESCRIPTION_TOO_SHORT:   Final[str] = "course.description_too_short"
    DESCRIPTION_TOO_LONG:    Final[str] = "course.description_too_long"

    # --- photo gallery ---
    GALLERY_EMPTY:           Final[str] = "course.gallery_empty"
    GALLERY_TOO_LARGE:       Final[str] = "course.gallery_too_large"

    # --- syllabus ---
    SYLLABUS_EMPTY:         Final[str] = "course.syllabus_empty"

    # --- venue ---
    VENUE_EMPTY:     Final[str] = "course.venue_empty"

    # --- dates ---
    DATE_RANGE_INVALID:      Final[str] = "course.date_range_invalid"
    START_IN_PAST:           Final[str] = "course.start_in_past"

    # --- price / money ---
    PRICE_INVALID:           Final[str] = "course.price_invalid"
    CURRENCY_INVALID:        Final[str] = "course.currency_invalid"

    # --- capacity ---
    CAPACITY_INVALID:        Final[str] = "course.capacity_invalid"

    # --- deposit policy ---
    DEPOSIT_INVALID:         Final[str] = "course.deposit_invalid"

    # --- cancellation policy ---
    CANCELLATION_INVALID:    Final[str] = "course.cancellation_invalid"

    # --- enrollment / price breakdown ---
    STUDENTS_INVALID:        Final[str] = "course.students_invalid"

    # --- category ---
    CATEGORY_EMPTY:       Final[str] = "course.category_empty"
    CATEGORY_TOO_LONG:    Final[str] = "course.category_too_long"

    # --- lifecycle / cross-entity ---
    ACADEMY_NOT_FOUND:        Final[str] = "course.academy_not_found"
    ALREADY_ARCHIVED:        Final[str] = "course.already_archived"
    HAS_ACTIVE_ENROLLMENTS: Final[str] = "course.has_active_enrollments"
    NOT_FOUND:               Final[str] = "course.not_found"
    INVALID_STATUS:          Final[str] = "course.invalid_status"
    INVALID_TRANSITION:      Final[str] = "course.invalid_transition"
    OVERLAP:                 Final[str] = "course.overlap"


class MoneyErrorCodes:
    AMOUNT_REQUIRED:          Final[str] = "money.amount_required"
    AMOUNT_INVALID:           Final[str] = "money.amount_invalid"
    AMOUNT_NEGATIVE:          Final[str] = "money.amount_negative"
    AMOUNT_TOO_MANY_DECIMALS: Final[str] = "money.amount_too_many_decimals"
    CURRENCY_INVALID:         Final[str] = "money.currency_invalid"