import requests, hashlib, datetime
from django.utils import timezone

DETAIL_KEY = "LKJHGTY&^%$$#)hfdrtTT(!@@##ASDFASDF6876789a!@#$%^&*"
PHOTO_KEY = "alksdjfl;jad*(^%%$%^**(!@@##ASDFASDF6876789191ahaga@@@#$%"


def get_student_details(email):
    email = email.replace("@iitbhu.ac.in", "@itbhu.ac.in")
    date_string = datetime.datetime.now().strftime("%Y-%m-%d")
    text = date_string + DETAIL_KEY + "-" + email
    sha1_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
    enc = hashlib.md5(sha1_hash.encode("utf-8")).hexdigest()
    print("TEXT =", text)
    print("SHA1 =", sha1_hash)
    print("ENC =", enc)
    response = requests.post(
        "https://examination.iitbhu.ac.in/api/std_details_api.php",
        data={"stdinfo": email, "enc": enc}, timeout=20,
    )
    print("STATUS CODE =", response.status_code)
    print("HEADERS:", response.headers)
    print("RESPONSE TEXT =", repr(response.text))
    return response.text


def get_photo_url(roll_no):
    text = PHOTO_KEY + "#" + roll_no
    enc = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return f"https://examination.iitbhu.ac.in/profile/get_photograph.php?rollno={roll_no}&enc={enc}"


def get_spi_cpi(roll_no, year_sem):
    dt = timezone.now().strftime("%Y-%m-%d")
    text = roll_no + dt + year_sem
    enc = hashlib.md5(hashlib.sha1(text.encode()).hexdigest().encode()).hexdigest()
    url = f"https://academicservices.iitbhu.ac.in/studnt_acad/spi_cpi/{roll_no}/{year_sem}/{enc}/"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()

