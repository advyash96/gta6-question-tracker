"""Tag each question with the GTA 6 topics it's about, using keyword rules (no AI).

Edit TOPICS to add your own categories. A question can match several topics;
anything that matches none is tagged "Other".
"""
import re

TOPICS = {
    "Release date / delays": r"release|come out|coming out|launch|delay|postpone|when (is|will|does)|\bdate\b|2026|2027|countdown",
    "PC version": r"\bpc\b|steam|epic games|windows|\bport(ed)?\b",
    "Consoles / platforms": r"ps5|ps4|playstation|xbox|series [xs]|switch|console|platform|pro\b",
    "Price / editions": r"price|cost|\$|\d+\s?(usd|dollars|bucks)|pre-?order|edition|preorder|how much",
    "Trailers / marketing": r"trailer|teaser|screenshot|gameplay reveal|showcase|announcement",
    "Story & characters": r"lucia|jason|character|protagonist|story|plot|ending|cast|voice actor",
    "Map & setting": r"map|leonida|vice city|miami|florida|keys|swamp|size|cities|city",
    "Online / multiplayer": r"online|multiplayer|gta\s?online|co-?op|servers|roleplay|\brp\b",
    "Gameplay & features": r"gameplay|gunplay|\bguns?\b|shoot|combat|mission|heist|\brob|\bcars?\b|vehicle|weapon|police|wanted|interior|customi[sz]|physics|ai\b|npc|first.?person|activit|\beat\b|drink|radio",
    "Graphics & performance": r"graphic|hdr|fps|frame.?rate|60\s?fps|30\s?fps|resolution|4k|ray.?trac|performance|run on|specs|requirement",
    "Leaks & rumors": r"leak|rumou?r|insider|fake|real\?|confirmed|legit",
    "Mods": r"\bmods?\b|modding|fivem",
}
_COMPILED = {name: re.compile(rx, re.I) for name, rx in TOPICS.items()}


def tag(text: str) -> list[str]:
    # Only look at the start (title + first lines): long rants otherwise match every topic.
    head = (text or "")[:250]
    hits = [name for name, rx in _COMPILED.items() if rx.search(head)]
    return hits or ["Other"]
