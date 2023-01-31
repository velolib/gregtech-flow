# Script to case insensitivify string separated by comma space
# Because JSON Schema doesn't support the flag.
import typer

def main(strings: str):
    for string in strings.split(', '):
        words = string.split(' ')
        for idx, word in enumerate(words):
            ins_word = ''
            for letter in word:
                ins_word += f'[{letter.upper()}{letter.lower()}]' if letter.isalpha() else letter
            words[idx] = ins_word
        result = ' '.join(words)
        print(result)

if __name__ == '__main__':
    typer.run(main)