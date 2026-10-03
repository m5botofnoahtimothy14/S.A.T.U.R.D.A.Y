"""SATURDAY Verse — offline daily verse + lookup. No network, no API.

Curated public-domain (KJV) verses. verse_of_day() rotates by date;
verse_lookup("23:1") finds by reference. Honest miss when unknown.
"""

VERSES = [
    ("Psalm 23:1", "The Lord is my shepherd; I shall not want."),
    ("Psalm 23:4", "Yea, though I walk through the valley of the shadow of death, I will fear no evil: for thou art with me."),
    ("Psalm 46:1", "God is our refuge and strength, a very present help in trouble."),
    ("Psalm 46:10", "Be still, and know that I am God."),
    ("Psalm 91:1", "He that dwelleth in the secret place of the most High shall abide under the shadow of the Almighty."),
    ("Psalm 121:1-2", "I will lift up mine eyes unto the hills, from whence cometh my help. My help cometh from the Lord."),
    ("Proverbs 3:5", "Trust in the Lord with all thine heart; and lean not unto thine own understanding."),
    ("Proverbs 3:6", "In all thy ways acknowledge him, and he shall direct thy paths."),
    ("Proverbs 16:3", "Commit thy works unto the Lord, and thy thoughts shall be established."),
    ("Isaiah 40:31", "They that wait upon the Lord shall renew their strength; they shall mount up with wings as eagles."),
    ("Isaiah 41:10", "Fear thou not; for I am with thee: be not dismayed; for I am thy God."),
    ("Jeremiah 29:11", "For I know the thoughts that I think toward you, saith the Lord, thoughts of peace, and not of evil, to give you an expected end."),
    ("Matthew 11:28", "Come unto me, all ye that labour and are heavy laden, and I will give you rest."),
    ("Matthew 6:33", "Seek ye first the kingdom of God, and his righteousness; and all these things shall be added unto you."),
    ("Mark 11:24", "What things soever ye desire, when ye pray, believe that ye receive them, and ye shall have them."),
    ("John 3:16", "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life."),
    ("John 14:27", "Peace I leave with you, my peace I give unto you: not as the world giveth, give I unto you."),
    ("Romans 8:28", "All things work together for good to them that love God."),
    ("Romans 15:13", "Now the God of hope fill you with all joy and peace in believing."),
    ("1 Corinthians 16:14", "Let all your things be done with charity."),
    ("Philippians 4:6", "Be careful for nothing; but in every thing by prayer and supplication with thanksgiving let your requests be made known unto God."),
    ("Philippians 4:13", "I can do all things through Christ which strengtheneth me."),
    ("Philippians 4:19", "My God shall supply all your need according to his riches in glory by Christ Jesus."),
    ("2 Timothy 1:7", "God hath not given us the spirit of fear; but of power, and of love, and of a sound mind."),
    ("Hebrews 11:1", "Faith is the substance of things hoped for, the evidence of things not seen."),
    ("James 1:5", "If any of you lack wisdom, let him ask of God, that giveth to all men liberally."),
    ("1 Peter 5:7", "Casting all your care upon him; for he careth for you."),
    ("1 John 4:18", "Perfect love casteth out fear."),
]


def verse_of_day(day=None) -> str:
    import datetime as _dt

    n = (day if day is not None else _dt.date.today().toordinal()) % len(VERSES)
    ref, text = VERSES[n]
    return f"{ref} - {text}"


def verse_lookup(ref: str) -> str:
    key = (ref or "").strip().lower().replace(" ", "")
    for r, text in VERSES:
        if key and key in r.lower().replace(" ", ""):
            return f"{r} - {text}"
    known = ", ".join(r for r, _ in VERSES[:8])
    return (f"Verse {ref!r} isn't in my pocket book yet. "
            f"Try one of: {known} ... (say 'verse' for today's)")
