"""
What it does: Sends the question and five chunks to Groq with the fixed grounded prompt.
Why it exists: This is the step that writes the answer, the citation, and the refusal.
What breaks without it: There is no answer, or the answer is not tied to the documents.
Failure stage: generation.
"""
