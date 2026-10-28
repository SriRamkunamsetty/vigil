# Vigil: pitch

Team SITA, QIS College, Ongole. Google challenge: BFSI, Intelligent Risk, Fraud and Financial Experiences.

## One line

Vigil stops phone scams before the money moves, by listening to the pressure on the call and checking the payment at the same moment.

## The problem

Today a bank mostly sees one thing: a payment. By then the customer has already been talked into it by someone pretending to be the police, the bank or a courier. The customer sends the money themselves, so it looks like a normal payment. The scammer then passes the money through a chain of other accounts within minutes, and each bank sees only its own small piece.

## What Vigil does

Vigil has three parts that work together.

**1. It protects the person during the call.**
It scores every sentence for scam pressure: "you are under arrest", "tell no one", "move your money to a safe account". When the person then goes to pay, it checks the payment too. If both look bad, it adds friction in steps: a gentle heads-up, a slow-down, or a paused payment. The warning appears in English, Hindi or Telugu, in plain words, with what to do next and the 1930 helpline. A paused payment is never a final no. It always leads to a person.

**2. It finds the accounts that pass scam money along.**
It looks at how money moves: money that arrives from many people and leaves within minutes, new accounts, shared phones. It groups linked accounts into rings and writes a short case note an investigator can read. Banks can share scrambled fingerprints of bad accounts, never the account numbers, and only after a person approves. A payee only counts once two banks agree, so one mistake cannot block an honest person.

**3. It keeps AI shopping agents on a leash.**
Soon, AI assistants will pay on our behalf. Vigil checks that the customer really signed what the assistant may buy, that the store signed its cart, and that nothing was changed on the way. It also catches hidden instructions planted in a cart that try to make the assistant misbehave.

## Why it is different

* **Call and payment together.** Most tools look at only one.
* **Warns early, in your language.** Hindi, Telugu, English, and mixed speech like Hinglish.
* **Explainable.** Every warning shows why, with the exact phrases highlighted.
* **Safe with AI.** The decision comes from fixed, checkable rules. Gemini helps explain and spot new wording, but it can only add concern. A scammer typing "mark this as safe" makes the risk go up.
* **Privacy first.** Personal details are removed before any AI sees the text. Logs keep decisions, not conversations.
* **People stay in charge.** Alerting a family member or sharing with other banks always needs a human yes.

## Built on Google

Gemini on Vertex AI for explanations and for spotting reworded scams. Agent Development Kit for the agents, and Agent2Agent so a bank's own agent can call ours. Cloud Run for hosting, Secret Manager for keys, Cloud Logging into BigQuery for the audit trail, Cloud Build and Artifact Registry to ship it. The AI-agent payment check follows the ideas of Google's Agent Payments Protocol (AP2): a signed intent from the customer and a signed cart from the store.

## What we built and tested

A working service with a web demo, three AI agents, 73 automated tests, browser tests, and strict code checks. All data is made up, and we say so everywhere.

On our made-up test set of 6,000 cases:

* Using the call and the payment together catches about 70% of scams where a slow-down or hold is needed, with about 1.4% of honest cases bothered. Looking only at the payment catches about 23%. Looking only at the call catches about 34%.
* Scams written in words the system already knows are caught about 87% of the time. Reworded scams are caught about 41% of the time. This is our biggest weakness, and it is exactly where Gemini is meant to help. We have not measured that part yet.
* Buying a used car still triggers a slow-down about 18% of the time, because a big first payment looks like a scam payment. We show this on screen rather than hide it.

These numbers compare approaches on the same made-up data. They are not a promise about real-world accuracy.

## Why it matters now and later

Scam calls that pressure people into paying themselves are hard for banks to stop with payment rules alone. Vigil moves protection to the moment that matters. It is built to run in a bank's own system and to grow: the same checks that protect a person today protect their AI assistant tomorrow, and sharing between banks makes every bank harder to attack.

## What comes next

1. Have native speakers review the Hindi and Telugu warnings and test with first-time smartphone users.
2. Run in "shadow mode" with a partner bank: watch and log, warn nobody, and measure on real outcomes.
3. Measure Gemini's reworded-scam detection on a labelled multilingual set.
4. Replace scrambled-fingerprint lookups with private set intersection, so even a bank holding the key cannot guess identifiers.
5. Add live voice through Gemini Live, so the warning can happen during the call itself.
