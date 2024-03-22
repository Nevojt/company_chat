import csv
import string



def load_banned_words(filename):
    banned_words = set()
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            # Видаляємо пробіли і переводи рядка
            word = line.strip()
            if word:  # Перевіряємо, що рядок не пустий
                banned_words.add(word.lower())
                # print(f"Додано слово: {word}")  # Діагностичний вивід
    return banned_words

# banned_words = load_banned_words(filename)
def censor_message(message, banned_words):
    words = message.split()
    censored_words = []
    for word in words:
        # Видалення пунктуації зі слова
        clean_word = word.lower().strip(string.punctuation)
        if clean_word in banned_words:
            censored_word = "*" * len(word)
        else:
            censored_word = word
        censored_words.append(censored_word)
        # print(f"Перевіряємо слово: {word} - {'Замінено' if censored_word == '*' * len(word) else 'Не замінено'}")  # Діагностичний вивід

    return ' '.join(censored_words)

