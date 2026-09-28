from datetime import date
import unittest

from domain.payment_recurrence import PaymentRecurrenceRule, occurrence_on_or_after


class PaymentRecurrenceTests(unittest.TestCase):
    def test_weekly_rule_supports_multiple_weekdays(self):
        rule = PaymentRecurrenceRule(frequency="WEEKLY", weekdays=[0, 2])
        self.assertEqual(occurrence_on_or_after(rule, date(2026, 8, 3), date(2026, 8, 4)), date(2026, 8, 5))

    def test_weekly_rule_requires_at_least_one_weekday(self):
        with self.assertRaises(ValueError):
            PaymentRecurrenceRule(frequency="WEEKLY")

    def test_month_end_uses_last_available_day(self):
        rule = PaymentRecurrenceRule(frequency="MONTHLY", day_of_month=31)
        self.assertEqual(occurrence_on_or_after(rule, date(2026, 1, 31), date(2026, 2, 1)), date(2026, 2, 28))

    def test_non_leap_year_uses_february_last_day(self):
        rule = PaymentRecurrenceRule(frequency="YEARLY")
        self.assertEqual(occurrence_on_or_after(rule, date(2024, 2, 29), date(2025, 1, 1)), date(2025, 2, 28))

    def test_fifth_weekday_means_last_weekday_of_month(self):
        rule = PaymentRecurrenceRule(frequency="MONTHLY", monthly_mode="NTH_WEEKDAY", week_ordinal=5, weekday=1)
        self.assertEqual(occurrence_on_or_after(rule, date(2026, 1, 27), date(2026, 2, 1)), date(2026, 2, 24))


if __name__ == "__main__":
    unittest.main()
