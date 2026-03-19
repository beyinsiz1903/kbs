import re
from typing import Tuple, Dict, Any
from datetime import datetime


def validate_tc_kimlik(tc_no: str) -> Tuple[bool, str]:
    """
    Validate Turkish Citizen Identity Number (TC Kimlik No).
    
    Rules:
    1. Must be exactly 11 digits
    2. First digit cannot be 0
    3. ((sum of digits at positions 1,3,5,7,9) * 7 - (sum of digits at positions 2,4,6,8)) % 10 == digit at position 10
    4. (sum of first 10 digits) % 10 == digit at position 11
    """
    if not tc_no:
        return False, "TC Kimlik numarasi bos olamaz / TC ID number cannot be empty"
    
    # Remove spaces
    tc_no = tc_no.strip()
    
    if not tc_no.isdigit():
        return False, "TC Kimlik numarasi sadece rakam icermelidir / TC ID must contain only digits"
    
    if len(tc_no) != 11:
        return False, f"TC Kimlik numarasi 11 hane olmalidir (mevcut: {len(tc_no)}) / TC ID must be 11 digits (current: {len(tc_no)})"
    
    if tc_no[0] == '0':
        return False, "TC Kimlik numarasinin ilk hanesi 0 olamaz / First digit of TC ID cannot be 0"
    
    digits = [int(d) for d in tc_no]
    
    # Checksum validation - 10th digit
    odd_sum = sum(digits[i] for i in range(0, 9, 2))  # positions 1,3,5,7,9 (0-indexed: 0,2,4,6,8)
    even_sum = sum(digits[i] for i in range(1, 8, 2))  # positions 2,4,6,8 (0-indexed: 1,3,5,7)
    check_10 = (odd_sum * 7 - even_sum) % 10
    
    if check_10 != digits[9]:
        return False, "TC Kimlik numarasi kontrol hanesi gecersiz / TC ID checksum digit 10 is invalid"
    
    # Checksum validation - 11th digit
    check_11 = sum(digits[:10]) % 10
    if check_11 != digits[10]:
        return False, "TC Kimlik numarasi kontrol hanesi gecersiz / TC ID checksum digit 11 is invalid"
    
    return True, "Gecerli / Valid"


def validate_passport(passport_no: str, country_code: str = None, expiry_date: str = None) -> Tuple[bool, str]:
    """
    Validate passport number with basic rules.
    
    Rules:
    1. Must not be empty
    2. Must be alphanumeric
    3. Length 5-20 characters
    4. Country code must be 2-3 letters if provided
    5. Expiry date must be in future if provided
    """
    if not passport_no:
        return False, "Pasaport numarasi bos olamaz / Passport number cannot be empty"
    
    passport_no = passport_no.strip().upper()
    
    if not re.match(r'^[A-Z0-9]{5,20}$', passport_no):
        return False, "Pasaport numarasi 5-20 alfanumerik karakter olmalidir / Passport number must be 5-20 alphanumeric characters"
    
    if country_code:
        country_code = country_code.strip().upper()
        if not re.match(r'^[A-Z]{2,3}$', country_code):
            return False, "Ulke kodu 2-3 harf olmalidir / Country code must be 2-3 letters"
    
    if expiry_date:
        try:
            expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
            if expiry < datetime.now():
                return False, "Pasaport suresi dolmus / Passport has expired"
        except ValueError:
            return False, "Gecersiz tarih formati (YYYY-MM-DD bekleniyor) / Invalid date format (expected YYYY-MM-DD)"
    
    return True, "Gecerli / Valid"


def validate_guest_data(guest_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate guest data based on guest type.
    """
    guest_type = guest_data.get("guest_type", "")
    
    if not guest_data.get("first_name"):
        return False, "Ad bos olamaz / First name cannot be empty"
    
    if not guest_data.get("last_name"):
        return False, "Soyad bos olamaz / Last name cannot be empty"
    
    if guest_type == "tc_citizen":
        tc_no = guest_data.get("tc_kimlik_no", "")
        return validate_tc_kimlik(tc_no)
    elif guest_type == "foreign":
        passport_no = guest_data.get("passport_no", "")
        country_code = guest_data.get("passport_country", "")
        expiry_date = guest_data.get("passport_expiry", "")
        
        if not guest_data.get("nationality"):
            return False, "Uyruk bos olamaz / Nationality cannot be empty"
        
        return validate_passport(passport_no, country_code, expiry_date)
    else:
        return False, f"Gecersiz misafir tipi: {guest_type} / Invalid guest type: {guest_type}"


def generate_fingerprint(guest_data: Dict[str, Any], hotel_id: str, checkin_date: str) -> str:
    """
    Generate a fingerprint for duplicate prevention.
    Combines guest identity + hotel + date into a unique key.
    """
    import hashlib
    
    guest_type = guest_data.get("guest_type", "")
    if guest_type == "tc_citizen":
        identity = guest_data.get("tc_kimlik_no", "")
    else:
        identity = f"{guest_data.get('passport_no', '')}_{guest_data.get('passport_country', '')}"
    
    raw = f"{hotel_id}|{identity}|{checkin_date}"
    return hashlib.sha256(raw.encode()).hexdigest()
