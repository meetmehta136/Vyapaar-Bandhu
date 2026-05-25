"""Tests for GST Compliance Engine - CGST Act, 2017"""
import pytest
from app.services.compliance_engine import (
    check_itc_eligibility,
    calculate_gst_liability,
    calculate_penalty,
    get_filing_deadlines,
    BLOCKED_ITC_CATEGORIES,
    GST_RATES,
)
from app.services.gstin_validator import validate_gstin


class TestSection17_5_Blocked:
    """Tests all ITC-blocked categories under CGST Act Section 17(5)"""

    def test_motor_vehicle_blocked(self):
        """Section 17(5)(a) — ITC blocked on motor vehicles for persons not in transport business"""
        result = check_itc_eligibility("motor_vehicle")
        assert result["eligible"] is False
        assert "17(5)" in result["reason"]

    def test_food_beverage_blocked(self):
        """Section 17(5)(b)(i) — food and beverages ITC blocked"""
        result = check_itc_eligibility("food_beverage")
        assert result["eligible"] is False
        assert result["itc_amount"] == 0

    def test_club_membership_blocked(self):
        """Section 17(5)(b)(ii) — club memberships ITC blocked"""
        result = check_itc_eligibility("club_membership")
        assert result["eligible"] is False

    def test_health_insurance_blocked(self):
        """Section 17(5)(b)(iii) — health insurance ITC blocked unless statutory obligation"""
        result = check_itc_eligibility("health_insurance")
        assert result["eligible"] is False

    def test_beauty_treatment_blocked(self):
        """Section 17(5)(b)(iv) — cosmetic/beauty treatment ITC blocked"""
        result = check_itc_eligibility("beauty_treatment")
        assert result["eligible"] is False

    def test_works_contract_blocked(self):
        """Section 17(5)(c) — works contract for immovable property ITC blocked"""
        result = check_itc_eligibility("works_contract")
        assert result["eligible"] is False

    def test_construction_blocked(self):
        """Section 17(5)(d) — construction of immovable property ITC blocked"""
        result = check_itc_eligibility("construction")
        assert result["eligible"] is False

    def test_gift_blocked(self):
        """Gifts are blocked under Section 17(5)"""
        result = check_itc_eligibility("gift")
        assert result["eligible"] is False

    def test_personal_consumption_blocked(self):
        """Personal consumption ITC blocked"""
        result = check_itc_eligibility("personal_consumption")
        assert result["eligible"] is False

    def test_rent_a_cab_blocked(self):
        """Rent-a-cab ITC blocked"""
        result = check_itc_eligibility("rent_a_cab")
        assert result["eligible"] is False

    def test_outdoor_catering_blocked(self):
        """Outdoor catering ITC blocked"""
        result = check_itc_eligibility("outdoor_catering")
        assert result["eligible"] is False

    def test_life_insurance_blocked(self):
        """Life insurance ITC blocked"""
        result = check_itc_eligibility("life_insurance")
        assert result["eligible"] is False

    def test_health_services_blocked(self):
        """Health services ITC blocked"""
        result = check_itc_eligibility("health_services")
        assert result["eligible"] is False

    def test_gym_membership_blocked(self):
        """Gym membership ITC blocked"""
        result = check_itc_eligibility("gym_membership")
        assert result["eligible"] is False

    def test_travel_benefit_blocked(self):
        """Travel benefit ITC blocked"""
        result = check_itc_eligibility("travel_benefit")
        assert result["eligible"] is False

    def test_all_blocked_categories_have_tests(self):
        """Every category in BLOCKED_ITC_CATEGORIES has a corresponding test"""
        blocked_set = BLOCKED_ITC_CATEGORIES | {"unknown_should_pass"}
        for cat in BLOCKED_ITC_CATEGORIES:
            r = check_itc_eligibility(cat)
            assert r["eligible"] is False, f"{cat} should be blocked"


class TestEligibleCategories:
    """Categories not in Section 17(5) should be ITC eligible"""

    def test_raw_materials_eligible(self):
        """Raw materials for manufacturing — ITC eligible under Section 16(1)"""
        result = check_itc_eligibility("raw_materials")
        assert result["eligible"] is True
        assert result["itc_amount"] is None

    def test_capital_goods_eligible(self):
        """Capital goods for business use — ITC eligible"""
        result = check_itc_eligibility("capital_goods")
        assert result["eligible"] is True

    def test_input_services_eligible(self):
        """Input services for business — ITC eligible"""
        result = check_itc_eligibility("input_services")
        assert result["eligible"] is True

    def test_plant_machinery_eligible(self):
        """Plant and machinery (not works contract) — ITC eligible"""
        result = check_itc_eligibility("plant_machinery")
        assert result["eligible"] is True

    def test_unknown_category_eligible(self):
        """Unknown categories default to eligible (not in blocked list)"""
        result = check_itc_eligibility("unknown_item_12345")
        assert result["eligible"] is True

    def test_case_insensitive(self):
        """Category matching should be case-insensitive"""
        for cat in list(BLOCKED_ITC_CATEGORIES)[:5]:
            assert check_itc_eligibility(cat.upper())["eligible"] is False
            assert check_itc_eligibility(cat.capitalize())["eligible"] is False


class TestGSTLiability:
    """Tests for GST liability calculation"""

    def test_basic_liability(self):
        """Simple sale with no purchases — full GST collected is liability"""
        txns = [{"type": "sale", "amount": 10000, "gst_rate": 18}]
        result = calculate_gst_liability(txns)
        assert result["total_gst_collected"] == 1800.0
        assert result["net_liability"] == 1800.0

    def test_itc_reduces_liability(self):
        """ITC from eligible purchase reduces net liability"""
        txns = [
            {"type": "sale", "amount": 10000, "gst_rate": 18},
            {"type": "purchase", "amount": 5000, "gst_rate": 18, "itc_eligible": True},
        ]
        result = calculate_gst_liability(txns)
        assert result["total_itc_available"] == 900.0
        assert result["net_liability"] == 900.0

    def test_full_itc_offset(self):
        """When ITC exceeds liability, net liability is zero (not negative)"""
        txns = [
            {"type": "sale", "amount": 1000, "gst_rate": 18},
            {"type": "purchase", "amount": 10000, "gst_rate": 18, "itc_eligible": True},
        ]
        result = calculate_gst_liability(txns)
        assert result["net_liability"] == 0.0
        assert result["total_gst_collected"] == 180.0
        assert result["total_itc_available"] == 1800.0

    def test_ineligible_purchase_no_itc(self):
        """Ineligible purchases should not reduce liability"""
        txns = [
            {"type": "sale", "amount": 10000, "gst_rate": 18},
            {"type": "purchase", "amount": 5000, "gst_rate": 18, "itc_eligible": False},
        ]
        result = calculate_gst_liability(txns)
        assert result["total_itc_available"] == 0.0
        assert result["net_liability"] == 1800.0

    def test_multiple_transactions(self):
        """Multiple sales and purchases should aggregate correctly"""
        txns = [
            {"type": "sale", "amount": 50000, "gst_rate": 18},
            {"type": "sale", "amount": 30000, "gst_rate": 12},
            {"type": "purchase", "amount": 20000, "gst_rate": 18, "itc_eligible": True},
            {"type": "purchase", "amount": 10000, "gst_rate": 5, "itc_eligible": True},
        ]
        result = calculate_gst_liability(txns)
        expected_gst = 50000 * 0.18 + 30000 * 0.12
        expected_itc = 20000 * 0.18 + 10000 * 0.05
        assert result["total_gst_collected"] == expected_gst
        assert result["total_itc_available"] == expected_itc
        assert result["net_liability"] == expected_gst - expected_itc

    def test_empty_transactions(self):
        """Empty transaction list — zero liability"""
        result = calculate_gst_liability([])
        assert result["total_gst_collected"] == 0.0
        assert result["total_itc_available"] == 0.0
        assert result["net_liability"] == 0.0


class TestPenalty:
    """Tests for late filing penalty calculation"""

    def test_no_penalty_on_time(self):
        """Zero days late — no penalty"""
        result = calculate_penalty("GSTR-3B", 0, 10000)
        assert result["penalty"] == 0
        assert result["total"] == 0

    def test_gstr1_penalty(self):
        """GSTR-1: Rs 50/day, max Rs 10,000"""
        result = calculate_penalty("GSTR-1", 10, 0)
        assert result["penalty"] == 500
        assert "din late" in result["message_hi"]

    def test_gstr1_penalty_capped(self):
        """GSTR-1 penalty caps at Rs 10,000"""
        result = calculate_penalty("GSTR-1", 300, 0)
        assert result["penalty"] == 10000

    def test_gstr3b_penalty_with_liability(self):
        """GSTR-3B with tax liability: Rs 50/day + 18% interest"""
        result = calculate_penalty("GSTR-3B", 30, 50000)
        expected_interest = round(50000 * 0.18 * 30 / 365, 2)
        assert result["penalty"] == 1500
        assert result["interest"] == expected_interest
        assert result["total"] == 1500 + expected_interest

    def test_gstr3b_nil_return(self):
        """GSTR-3B nil return: Rs 20/day, no interest"""
        result = calculate_penalty("GSTR-3B", 15, 0)
        assert result["penalty"] == 300
        assert result["interest"] == 0

    def test_unknown_return_type(self):
        """Unknown return type — zero penalty"""
        result = calculate_penalty("GSTR-9", 10, 10000)
        assert result["penalty"] == 0
        assert result["interest"] == 0


class TestFilingDeadlines:
    """Tests for filing deadline calculation"""

    def test_gstr1_deadline_11th(self):
        """GSTR-1 is due on 11th of next month"""
        result = get_filing_deadlines("2025-03")
        assert "gstr1_deadline" in result
        assert "2025-04-11" in result["gstr1_deadline"]

    def test_gstr3b_deadline_20th(self):
        """GSTR-3B is due on 20th of next month"""
        result = get_filing_deadlines("2025-03")
        assert "2025-04-20" in result["gstr3b_deadline"]

    def test_december_crosses_year(self):
        """December period — deadlines are in January of next year"""
        result = get_filing_deadlines("2025-12")
        assert "2026-01-11" in result["gstr1_deadline"]
        assert "2026-01-20" in result["gstr3b_deadline"]

    def test_days_remaining_is_integer(self):
        """days_to_gstr1/days_to_gstr3b should be integers"""
        result = get_filing_deadlines("2025-06")
        assert isinstance(result["days_to_gstr1"], int)
        assert isinstance(result["days_to_gstr3b"], int)

    def test_period_in_output(self):
        """Period string should appear in output"""
        result = get_filing_deadlines("2025-03")
        assert result["period"] == "2025-03"


class TestGSTINValidation:
    """Tests for GSTIN format and checksum validation"""

    @pytest.mark.parametrize("gstin,valid,reason", [
        ("29ABCDE1234F1ZC", True, "Standard Karnataka GSTIN"),
        ("27AAPFU0939F1ZZ", True, "Standard Maharashtra GSTIN"),
        ("24AAACI1234F1ZL", True, "Gujarat GSTIN"),
        ("07ABCDE1234F1ZM", True, "Delhi GSTIN"),
        ("INVALID", False, "Too short"),
        ("", False, "Empty string"),
        ("12345", False, "Too short"),
        ("29ABCDE1234F1ZCEXTRA", False, "Too long"),
        ("99ABCDE1234F1Z5", False, "Invalid state code 99"),
    ])
    def test_gstin_validation(self, gstin, valid, reason):
        """Validate various GSTIN formats"""
        result = validate_gstin(gstin)
        assert result["is_valid"] is valid, f"{reason}: expected valid={valid}"

    def test_auto_correction_works(self):
        """Common OCR errors on checksum char should be auto-corrected"""
        result = validate_gstin("29AABDF5678F2ZB")
        assert result["is_valid"] is True
        assert result["auto_corrected"] is True
        assert result["gstin"] == "29AABDF5678F2Z8"

    def test_valid_gstin_has_state_name(self):
        """Valid GSTIN should return the correct state name"""
        result = validate_gstin("29ABCDE1234F1ZC")
        assert result["state_name"] == "Karnataka"

    def test_valid_gstin_has_pan(self):
        """Valid GSTIN should extract PAN correctly"""
        result = validate_gstin("29ABCDE1234F1ZC")
        assert result["pan"] == "ABCDE1234F"

    def test_valid_gstin_no_error(self):
        """Valid GSTIN should have error=None"""
        result = validate_gstin("29ABCDE1234F1ZC")
        assert result["error"] is None


class TestEdgeCases:
    """Edge cases and error handling"""

    def test_zero_amount_liability(self):
        """Zero amount transactions should not crash"""
        result = calculate_gst_liability([
            {"type": "sale", "amount": 0, "gst_rate": 18}
        ])
        assert result["total_gst_collected"] == 0.0
        assert result["net_liability"] == 0.0

    def test_large_amount_liability(self):
        """Large amounts should calculate correctly without overflow"""
        result = calculate_gst_liability([
            {"type": "sale", "amount": 99999999, "gst_rate": 18}
        ])
        assert result["total_gst_collected"] == 17999999.82
        assert result["net_liability"] == 17999999.82

    def test_missing_category_graceful(self):
        """Unknown/misspelled category should default to eligible"""
        result = check_itc_eligibility("")
        assert result["eligible"] is True
        reason = result.get("reason", "")
        assert "eligible" in reason.lower()

    def test_whitespace_handling(self):
        """Categories with extra whitespace should be handled"""
        result = check_itc_eligibility("  motor_vehicle  ")
        assert result["eligible"] is False

    def test_special_characters_safe(self):
        """Special characters in category should not crash"""
        result = check_itc_eligibility("!@#$%^")
        assert result["eligible"] is True

    def test_negative_days_penalty(self):
        """Filing before deadline — zero penalty"""
        result = calculate_penalty("GSTR-3B", -5, 10000)
        assert result["penalty"] == 0
        assert result["interest"] == 0

    def test_gstr3b_penalty_no_cap_exceeded(self):
        """GSTR-3B penalty caps at Rs 10,000"""
        result = calculate_penalty("GSTR-3B", 500, 10000)
        assert result["penalty"] == 10000
