import requests
import hashlib
import datetime


DETAIL_KEY = "LKJHGTY&^%$$#)hfdrtTT(!@@##ASDFASDF6876789a!@#$%^&*"

PHOTO_KEY = "alksdjfl;jad*(^%%$%^**(!@@##ASDFASDF6876789191ahaga@@@#$%"


def get_student_details(email):

    email = email.replace(
        "@iitbhu.ac.in",
        "@itbhu.ac.in"
    )
    
    date_string = datetime.datetime.now().strftime(
        "%Y-%m-%d"
    )

    text = (
        date_string +
        DETAIL_KEY +
        "-" +
        email
    )

    sha1_hash = hashlib.sha1(
        text.encode("utf-8")
    ).hexdigest()

    enc = hashlib.md5(
        sha1_hash.encode("utf-8")
    ).hexdigest()

    print("TEXT =", text)
    print("SHA1 =", sha1_hash)
    print("ENC =", enc)
    
    response = requests.post(
        "https://examination.iitbhu.ac.in/api/std_details_api.php",
        data={
            "email": email,
            "enc": enc
        },
        timeout=20
    )

    #return response.json()
    print("STATUS CODE =", response.status_code)

    print("RESPONSE TEXT =")
    print(response.text)

    return response.text


def get_photo_url(roll_no):

    text = (
        PHOTO_KEY +
        "#" +
        roll_no
    )

    enc = hashlib.sha1(
        text.encode("utf-8")
    ).hexdigest()

    return (
        "https://examination.iitbhu.ac.in/profile/get_photograph.php"
        f"?rollno={roll_no}"
        f"&enc={enc}"
    )