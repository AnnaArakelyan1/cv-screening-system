"""
Run this inside the backend container:
  docker exec -it cv-screening-system-backend-1 python test_aspiration.py
"""
from utils.cv_parser import extract_skills, build_embedding_text

# ── English tests ────────────────────────────────────────────────────────────

cv_aspiration_en = """
John Doe
john@example.com

Objective:
I want to learn machine learning and I am eager to learn Python.
I am interested in learning Docker.

Experience:
Worked as a cashier at a supermarket.

Education:
High school diploma.
"""

cv_real_en = """
Jane Smith
jane@example.com

Experience:
3 years building machine learning models using Python and scikit-learn.
Deployed services with Docker on AWS.

Education:
BSc Computer Science, 2020.
"""

# ── Armenian tests ───────────────────────────────────────────────────────────

cv_aspiration_hy = """
Անի Սարգսյան
ani@example.com

Նպատակ:
Ուզում եմ սովորել Python և machine learning։
Հետաքրքրված եմ Docker-ով և AWS-ով։
Ձգտում եմ տիրապետել deep learning-ին։

Փորձ:
Աշխատել եմ որպես վաճառող խանութում։

Կրթություն:
Միջնակարգ կրթություն։
"""

cv_real_hy = """
Արամ Պետրոսյան
aram@example.com

Աշխատանքային փորձ:
3 տարի Python-ով backend մշակում FastAPI-ի և PostgreSQL-ի հետ։
Կիրառել եմ Docker և AWS cloud ծառայություններ։
Machine learning մոդելներ կառուցել scikit-learn-ի միջոցով։

Կրթություն:
Բակալավր, Երևանի Պետական Համալսարան, 2021թ։
"""

cv_mixed_hy = """
Մարիամ Հակոբյան
mariam@example.com

Աշխատանքային փորձ:
2 տարի Python-ով աշխատել եմ, REST API-ներ կառուցել FastAPI-ի հետ։

Նպատակ:
Ուզում եմ սովորել machine learning և deep learning։
Հետաքրքրված եմ Docker-ով։

Կրթություն:
Մագիստր, ՀՊՀ, 2022թ։
"""

# ── Run tests ────────────────────────────────────────────────────────────────

print("=" * 60)
print("TEST 1 — English aspirational only")
print("Expected: nothing")
print(f"Got: {extract_skills(cv_aspiration_en)}")

print()
print("=" * 60)
print("TEST 2 — English real experience")
print("Expected: python, machine learning, scikit-learn, docker, aws")
print(f"Got: {extract_skills(cv_real_en)}")

print()
print("=" * 60)
print("TEST 3 — Armenian aspirational only")
print("Expected: nothing (ուզում եմ սովորել / հետաքրքրված եմ should filter all)")
print(f"Got: {extract_skills(cv_aspiration_hy)}")

print()
print("=" * 60)
print("TEST 4 — Armenian real experience")
print("Expected: python, fastapi, postgresql, docker, aws, machine learning, scikit-learn")
print(f"Got: {extract_skills(cv_real_hy)}")

print()
print("=" * 60)
print("TEST 5 — Armenian mixed (real Python/FastAPI + aspirational ML/Docker)")
print("Expected: python, fastapi, rest api — machine learning and docker filtered out")
print(f"Got: {extract_skills(cv_mixed_hy)}")

print()
print("=" * 60)
print("TEST 6 — Armenian aspirational embedding text (no sections detected)")
parsed = {"skills": [], "experience": None, "education": None, "raw_text": cv_aspiration_hy}
emb = build_embedding_text(parsed)
print(f"Embedding text:\n{emb}")
print()
print("'ուզում եմ սովորել' NOT in embedding:", "ուզում եմ սովորել" not in emb)
print("'հետաքրքրված եմ' NOT in embedding:", "հետաքրքրված եմ" not in emb)
