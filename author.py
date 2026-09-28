"""Author data, shared by the Home tab, help texts and reports."""
FACULTY = "Facultad de Ingeniería y Ciencias"
UNIVERSITY = "Universidad Autónoma de Tamaulipas"

AUTHOR = {
    "name": "Daniel Ibarra-Marinas",
    "faculty": FACULTY,
    "university": UNIVERSITY,
    "email": "daniel.ibarra@uat.edu.mx",
    "orcid": "0000-0003-3683-4456",
    "github": "adanielibarra",
    "scholar": "https://scholar.google.com/citations?user=5JgVP2MAAAAJ&hl=en",
    "researchgate": "https://www.researchgate.net/profile/Daniel-Ibarra-Marinas",
}
# co-authors: only the data they have confirmed
COAUTHORS = [
    {"name": "Ana Mónica de Jhesú García",
     "faculty": FACULTY,
     "university": UNIVERSITY,
     "orcid": "0000-0001-6613-6945",
     "scholar": "https://scholar.google.com/citations?user=xOhHkwEAAAAJ&hl=es",
     "researchgate": "https://www.researchgate.net/profile/Ana-Garcia-Garcia-4"},
]
AUTHORS_TEXT = " and ".join([AUTHOR["name"]] + [c["name"] for c in COAUTHORS])
CREDIT = (f"StarShoal, by {AUTHORS_TEXT}, {FACULTY}, {UNIVERSITY}. Contact: {AUTHOR['email']}.")
