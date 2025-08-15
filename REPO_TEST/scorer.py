# scorer.py

from transformers import pipeline
import re
from nltk.stem import WordNetLemmatizer
from nltk.corpus import words as nltk_words
import nltk

# One-time downloads (uncomment and run ONCE, then comment out again):
# nltk.download('words')
# nltk.download('wordnet')

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
ENGLISH_WORDS = set(nltk_words.words())
lemmatizer = WordNetLemmatizer()

RESPONSIBILITY_PHRASES = [
    "admit", "admitted", "admitting", "admits",
    "acknowledge", "acknowledged", "acknowledges", "acknowledging",
    "confess", "confessed", "confesses", "confessing",
    "confide", "confided", "confides", "confiding",
    "responsible", "accountable", "accountability",
    "committed", "commitment", "obligation", "obligations",
    "duty", "obliged", "depend", "depends", "depended", "depending",
    "owe", "owes", "owed", "comply", "complied", "complies", "complying",
    "obedience", "obedient", "obey", "obeyed", "obeying", "obeys",
    "answerable", "fault", "at fault", "responsibility"
]

AVOIDANCE_PHRASES = [
    "avoid*", "ignor*", "neglect*", "deny*", "refus*", "reject*", "escape*", "evad*", "withdraw*", "excuse*", "hesitat*", "reluctan*", "disown*"
]
EXPLANATION_WORDS = {
    "because", "since", "therefore", "reason", "due to", "so that", "as a result", "consequently"
}
EXPLANATION_PHRASES = {
    "for this reason", "as a result", "the reason is", "the reason i", "as a consequence"
}
EVIDENCE_WORDS = {
    "evidence", "data", "proof", "support", "supporting",
    "research", "study", "studies", "found", "finding",
    "show", "shows", "shown", "indicate", "indicates",
    "demonstrate*", "result*", "statistic*", "fact*", "observ*",
    "verify", "verified", "validation", "justification"
}

def phrase_match_score(response, phrase_list):
    resp_lower = response.lower()
    matches = set(p for p in phrase_list if p in resp_lower)
    score = len(matches) / len(phrase_list) if phrase_list else 0
    return score, matches

def explanation_match_score(response):
    resp_lower = response.lower()
    word_matches = set([word for word in EXPLANATION_WORDS if f" {word} " in f" {resp_lower} "])
    phrase_matches = set([phrase for phrase in EXPLANATION_PHRASES if phrase in resp_lower])
    all_matches = word_matches.union(phrase_matches)
    score = 1.0 if all_matches else 0.0  # FULL credit for just any explanation
    return score, all_matches

def evidence_match_score(response):
    resp_lower = response.lower()
    matches = set([word for word in EVIDENCE_WORDS if word in resp_lower])
    score = 1.0 if matches else 0.0  # FULL credit if any evidence/feature used
    return score, matches

def fraction_real_words(response):
    tokens = re.findall(r'\w+', response.lower())
    real = [t for t in tokens if t in ENGLISH_WORDS]
    return len(real) / len(tokens) if tokens else 0.0

def is_coherent(response, threshold=0.9, print_confidence=False):
    labels = ["meaningful", "nonsense"]
    result = classifier(response, labels)
    scores = dict(zip(result['labels'], result['scores']))
    coherence_score = scores.get("meaningful", 0)
    f_real = fraction_real_words(response)
    if print_confidence:
        print(f"(Coherence confidence: {coherence_score:.2f}, Real word ratio: {f_real:.2f})")
    return coherence_score >= threshold and f_real > 0.6

def responsibility_score(response):
    real_word_ratio = fraction_real_words(response)
    pos_phrase_score, matched_pos = phrase_match_score(response, RESPONSIBILITY_PHRASES)
    neg_phrase_score, matched_neg = phrase_match_score(response, AVOIDANCE_PHRASES)
    explanation_score, matched_expl = explanation_match_score(response)
    evidence_score, matched_evidence = evidence_match_score(response)

    # Compute main score: credit for explanation, evidence, and positive phrases;
    # penalize for avoidance
    if real_word_ratio == 0 and (pos_phrase_score + explanation_score + evidence_score) == 0:
        final_score = 0.0
    else:
        composite_justification = pos_phrase_score + explanation_score + evidence_score
        avoidance_penalty = 1 - neg_phrase_score
        final_score = (real_word_ratio + composite_justification * avoidance_penalty) / 2
    final_score = min(1.0, round(final_score, 3))
    return final_score, matched_pos, matched_neg, matched_expl, matched_evidence, real_word_ratio, pos_phrase_score, neg_phrase_score, explanation_score, evidence_score

# Store scores
participant_scores = {}

if __name__ == '__main__':
    #participant_id = input("Enter participant ID: ")
    max_attempts = 2
    attempt = 0
    coherent = False
    response = ""
    while attempt < max_attempts and not coherent:
        response = input("Type your answer: ")
        coherent = is_coherent(response, print_confidence=True)
        if not coherent and attempt < max_attempts - 1:
            print("Your answer does not appear to be a meaningful sentence. Please try again.\n")
        attempt += 1
    if not coherent:
        print("Your answer may not be meaningful, but proceeding anyway.")

    score, matched_pos, matched_neg, matched_expl, matched_evidence, real_ratio, pos_score, neg_score, expl_score, ev_score = responsibility_score(response)
    print(f"\nResponsible phrases matched: {', '.join(sorted(matched_pos)) if matched_pos else 'None'}")
    print(f"Avoidance phrases matched: {', '.join(sorted(matched_neg)) if matched_neg else 'None'}")
    print(f"Explanation words/phrases matched: {', '.join(sorted(matched_expl)) if matched_expl else 'None'}")
    print(f"Evidence/features matched: {', '.join(sorted(matched_evidence)) if matched_evidence else 'None'}")
    print(f"Real word ratio: {real_ratio:.2f}, Responsible phrase ratio: {pos_score:.2f}, Avoidance phrase ratio: {neg_score:.2f}, Explanation: {expl_score:.2f}, Evidence: {ev_score:.2f}")
    print(f"Structured responsibility score (FINAL): {score}")

    participant_scores[participant_id] = {
        "response": response,
        "responsibility_score": score,
        "matched_responsibility_phrases": list(matched_pos),
        "matched_avoidance_phrases": list(matched_neg),
        "matched_explanation_words_phrases": list(matched_expl),
        "matched_evidence_words": list(matched_evidence),
        "real_word_ratio": real_ratio,
        "responsibility_phrase_ratio": pos_score,
        "avoidance_phrase_ratio": neg_score,
        "explanation_ratio": expl_score,
        "evidence_ratio": ev_score
    }
    with open("participant_scores.json", "w") as fp:
        json.dump(participant_scores, fp, indent=2)