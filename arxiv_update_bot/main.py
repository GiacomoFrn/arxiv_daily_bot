"""
Main file of the arxiv_update_bot module.

Contains the methods to read configuration,
fetch updates and send messages along with the cli.
"""
import argparse
import configparser
from typing import List, Tuple

import feedparser
import telebot
import os
import unicodedata
from rapidfuzz import fuzz

DEFAULT_CONFIGURATION_PATH = "./config.ini"

# pylint: disable=too-few-public-methods
class Update:
    """
    Class representing an update section in the configuration file.

    It is composed of a category, a chat id and a list of buzzwords.
    """

    chat_id: int  #: The chat id to send the update to.
    category: str  #: The arxiv category.
    buzzwords: List[str]  #: The list of buzzwords to trigger on.

    def __init__(self, config: dict) -> None:
        """Initialize the update instance.

        Args:
            config (dict): section of the configuration corresponding to the update.

        Raises:
            Exception: if the section is not complete (i.e. missing one of category, chat_id or buzzwords).
        
        if not ("category" in config and "chat_id" in config and "buzzwords" in config):
            raise Exception(
                f"The section {config} is not complete. Missing one of three : category, chat_id or buzzwords."
            )
        """
        self.category = config["category"]
        self.chat_id = os.environ["chat_id"]
        self.buzzwords = config["buzzwords"].split(",")


def load_config(path: str) -> Tuple[str, List[Update]]:
    """Load the configuration from the path.
    It will try to load the token from the [bot] section.
    Then it will iterate over the other sections to find the updates to verify.

    Args:
        path (string): path of the config file.

    Raises:
        Exception: if the bot section is not found.
        Exception: if there is no token value in the bot section.
        Exception: if an update section is not complete.

    Returns:
        (string, list): the token and the list of updates.
    """
    config = configparser.ConfigParser()
    config.read(path)
    """
    if "bot" not in config:
        raise Exception(
            "A bot section must be in the configuration file to set the token"
        )

    bot_config = config["bot"]
    if "token" not in bot_config:
        raise Exception("The bot section must have the bot token.")
    """
    token = os.environ["token"]
    updates = []
    for section in config.sections():
        if str(section) != "bot":
            updates.append(Update(config[section]))
    return token, updates


def normalize_name(name):
    # Normalize to NFKD form and remove diacritics
    nfkd_form = unicodedata.normalize('NFKD', name)
    without_accents = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
    return without_accents.lower().strip()


def is_name_match(name1, name2, threshold=90):
    # Returns True if the similarity ratio is above the threshold
    return fuzz.token_sort_ratio(name1, name2) >= threshold


def get_articles(category: str, buzzwords: List[str]) -> List:
    """Get the articles from arXiv.

    It get the RSS flux re;ated to the category of the update,
    then filter the entries with the buzzwords.

    Args:
        category (str): the name of the category.
        buzzwords (List[str]): a list of buzzwords.

    Returns:
        List: list of entries.
    """
    news_feed = feedparser.parse(f"https://rss.arxiv.org/rss/{category}")
    authors_to_watch = "Jakob Gunther, Antonio Acin, Federico Centrone, Hippolyte Dourdent, David Jansen, Tamás Kriváchy, Márcio M Taddei, Pere Mujal, Ignacio Perito, Ranieri Nery, Raja Yehia, Leonardo Zambrano, Maria Balanzó-Juandó, Júlia Barberà Rodríguez, Fionnuala Curran, Raffaele D'Avino, Francesco Flora, Giacomo Franceschetto, Timothy Heightman, Luke Mortimer, Mariana Navarro Asan-Srain, Egle Pagliaro, Teodor Parella-Dilmé, Erik Recio Armengol, Anna Steffinlongo, Emilio Annoni, Antonio Sannia, Tommaso Grigoletto, Hsin-Yuan Huang, Marcin P{\\l}odzie\\'n, Giacomo Franceschetto, Alexia Salavrakos, Arno Ricou, Joseph Bowles".split(', ')#os.environ["authors_to_watch"].split(', ')
    # Normalize the watchlist names once
    normalized_watchlist = [normalize_name(name) for name in authors_to_watch]
    
    res = []
    
    """
    if any(buzzword in entry.title.lower() for buzzword in buzzwords):
        res.append(entry)
    elif any(author in entry.authors[0]['name'].split(', ') for author in authors_to_watch):
        res.append(entry)
    """
    for entry in news_feed.entries:
        for author in entry.authors[0]['name'].split(', '):
            normalized_author = normalize_name(author)
            if author == "Jakob G\"unther":
                print(is_name_match(normalized_author, "Jakob Gunther"))
            if any(is_name_match(normalized_author, watch_name) for watch_name in normalized_watchlist) :#or any(buzzword in entry.title.lower() for buzzword in buzzwords):
                res.append(entry)
                break  # Avoid adding the same entry multiple times
    return res


def send_articles(
    bot: telebot.TeleBot,
    chat_id: int,
    category: str,
    buzzwords: List[str],
    quiet: bool = False,
) -> None:
    """Send the articles to telegram.

    Args:
        bot (telebot.Telebot): telebot instance.
        chat_id (int): the chat id to send the message. Either a group or individual.
        category (str): the category for arXiv.
        buzzwords (List[str]): list of buzzwords.
        quiet (bool, optional): whether to send a messae when no article is found. Defaults to False.
    """
    articles = get_articles(category, buzzwords)

    if not articles:
        if not quiet:
            bot.send_message(
                chat_id,
                text="Yo man, I scraped the arXiv RSS,\nBut nothing new for you, I must confess.\nMaybe arXiv is down or on vacation,\nThat's why I found no new information.\n\nBut don't you worry, I'll keep on searching,\nFor new knowledge, I'll keep on lurching.\nArXiv may be quiet, but I won't rest,\nUntil I find something that's truly the best.",
            )
    else:
        bot.send_message(
            chat_id,
            text=f'Yo, found {len(articles)} articles that might be dope, check em out!',
        )
        for article in articles:
            try:
                bot.send_message(
                    chat_id,
                    text="<strong>Title</strong>: " + article.title + "\n<strong>Authors</strong>: " + article.authors[0]['name'].replace('\\', '') + "\n<strong>Link</strong>: " + article.link,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except:
                continue


def main():
    """
    The main function.
    """
    parser = argparse.ArgumentParser(description="Scrap the arXiv")
    parser.add_argument(
        "-c",
        "--config-path",
        help="Path for configuration path. Replace default of /etc/arxiv-update-bot/config.ini",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="If quiet is set, then the bot will not send message if no article are found.",
    )
    parser.add_argument(
        "-p",
        "--print-info",
        action="store_true",
        help="If print-info is set, then the bot will send its configuration instead of the updates.",
    )

    args = parser.parse_args()
    config_path = args.config_path or DEFAULT_CONFIGURATION_PATH
    quiet = args.quiet

    token, updates = load_config(config_path)

    bot = telebot.TeleBot(token, parse_mode="HTML")

    for update in updates:
        if args.print_info:
            bot.send_message(
                update.chat_id,
                text=f"Hi there ! I am configured to send articles from category {update.category} with buzzwords {', '.join(update.buzzwords)}",
            )
        else:
            send_articles(
                bot,
                update.chat_id,
                update.category,
                update.buzzwords,
                quiet=quiet,
            )


if __name__ == "__main__":
    main()
