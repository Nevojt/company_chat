import csv
import string



def load_banned_words(filename):
    banned_words = set()
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            # Remove spaces and line breaks
            word = line.strip()
            if word:  # Check that the string is not empty
                banned_words.add(word.lower())
                
    return banned_words

# banned_words = load_banned_words(filename)
def censor_message(message, banned_words):
    words = message.split()
    censored_words = []
    for word in words:
        # Remove punctuation from a word
        clean_word = word.lower().strip(string.punctuation)
        if clean_word in banned_words:
            censored_word = "*" * len(word)
        else:
            censored_word = word
        censored_words.append(censored_word)
    
    return ' '.join(censored_words)

