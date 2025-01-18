import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# URL di base per gli annunci
BASE_URL = "https://www.immobiliare.it/vendita-case/torino/?criterio=data&ordine=desc"

# Headers per simulare un browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
}

# Token del bot di Telegram
TELEGRAM_TOKEN = "7915034690:AAF2kT5t6Xb4pfZyqirUR_yq4J7fCUB8lws"

# Lista degli ID chat autorizzati
AUTHORIZED_USERS = [
    "331032870",  # MOI
    "6735019784", # LUCA
    #"6735019784", # IDA
    #"6735019784", # VIOLINA
]

# Lista delle zone di Torino
ZONE_TORINO = {
    'Centro': ['centro', 'centro storico', 'palazzo reale', 'piazza castello', 'piazza solferino'],
    'Quadrilatero': ['quadrilatero'], 
    'Crocetta': ['crocetta', 'politecnico'],
    'San Salvario': ['san salvario', 'valentino', 'dante', 'baretti'],
    'San Secondo': ['san secondo'],
    'Vanchiglia': ['vanchiglia', 'borgo vanchiglia'],
    'Aurora': ['aurora', 'borgo dora'],
    'Barriera di Milano': ['barriera di milano', 'barriera milano', 'corso giulio cesare'],
    'Borgo Vittoria': ['borgata vittoria', 'borgo vittoria'],
    'San Donato': ['san donato'],
    'Campidoglio': ['campidoglio'],
    'Cenisia': ['cenisia'],
    'Cit Turin': ['cit turin'],
    'San Paolo': ['san paolo'],
    'Pozzo Strada': ['pozzo strada'],
    'Santa Rita': ['santa rita'],
    'Mirafiori Nord': ['mirafiori nord'],
    'Mirafiori Sud': ['mirafiori sud'],
    'Lingotto': ['lingotto'],
    'Nizza Millefonti': ['nizza millefonti'],
    'Filadelfia': ['filadelfia'],
    'Parella': ['parella'],
    'Borgo Po': ['borgo po'],
    'Cavoretto': ['cavoretto'],
    'Madonna del Pilone': ['madonna del pilone'],
    'Lucento': ['lucento'],
    'Le Vallette': ['le vallette', 'vallette'],
    'Regio Parco': ['regio parco'],
    'Falchera': ['falchera'],
    'Vanchiglietta': ['vanchiglietta'],
    'Gran Madre': ['gran madre'], 
    'Colle della Maddalena': ['colle della maddalena'], 
    'Superga': ['superga'], 
    'Borgo San Paolo': ['borgo san paolo'], 
    'Rebaudengo': ['rebaudengo'], 
    'Barriera di Lanzo': ['barriera di lanzo'], 
    'Falchera': ['falchera'] ,
    'Barca': ['barca'], 
    'Bertolla': ['bertolla'], 
    'Parco Dora': ['parco dora'], 
    'Madonna di Campagna': ['madonna di campagna'], 
    'Sassi': ['sassi'],
    'Cittadella': ['cittadella'], 
    # Aggiungi altre zone se necessario
}

# Aggiungi questa lista dopo ZONE_TORINO
ZONE_ESCLUSE = {
    'Mirafiori Nord',
    'Mirafiori Sud',
    # Aggiungi altre zone da escludere
}

# Crea un'istanza del bot
bot = Bot(token=TELEGRAM_TOKEN)

def extract_zona(location_text):
    """
    Estrae la zona da una stringa di localizzazione utilizzando la lista delle zone note
    """
    location_lower = location_text.lower()
    
    # Prima cerca le corrispondenze esatte nelle parentesi
    parentheses_match = re.search(r'\((.*?)\)', location_lower)
    if parentheses_match:
        parentheses_content = parentheses_match.group(1)
        for zona, keywords in ZONE_TORINO.items():
            if any(keyword in parentheses_content for keyword in keywords):
                return zona

    # Poi cerca dopo la parola "zona" o "quartiere"
    zona_match = re.search(r'(?:zona|quartiere)\s+([^,]+)', location_lower)
    if zona_match:
        zona_text = zona_match.group(1).strip()
        for zona, keywords in ZONE_TORINO.items():
            if any(keyword in zona_text for keyword in keywords):
                return zona

    # Infine cerca in tutta la stringa
    for zona, keywords in ZONE_TORINO.items():
        if any(keyword in location_lower for keyword in keywords):
            return zona

    # Se non trova corrispondenze
    return "Non specificata"

def extract_indirizzo(location_text):
    """
    Estrae l'indirizzo dalla stringa di localizzazione
    """
    # Rimuove la parte tra parentesi se presente
    indirizzo = re.sub(r'\s*\([^)]*\)', '', location_text)
    
    # Rimuove la parte dopo "zona" o "quartiere" se presente
    indirizzo = re.sub(r'\s*(?:zona|quartiere)\s+[^,]+', '', indirizzo)
    
    # Pulisce e restituisce la prima parte dell'indirizzo
    return indirizzo.split(',')[0].strip()

def calcola_prezzo_m2(row):
    try:
        if row['Prezzo'] != 'N/A' and row['Metri Quadri'] != 'N/A':
            # Gestisce il prezzo
            prezzo = row['Prezzo']
            # Rimuove il simbolo €, spazi e la parola "da"
            prezzo = prezzo.replace('€', '').replace('da', '').strip()
            # Se c'è una virgola, prendi solo la parte prima della virgola
            prezzo = prezzo.split(',')[0]
            # Rimuove i punti e converte in intero
            prezzo_numerico = int(prezzo.replace('.', ''))
            
            # Gestisce i metri quadri
            metri = row['Metri Quadri']
            # Rimuove "m²" e spazi
            metri = metri.replace('m²', '').strip()
            # Se c'è una virgola, prendi solo la parte prima della virgola
            metri = metri.split(',')[0]
            # Rimuove i punti e converte in intero
            metri_quadri_numerico = int(metri.replace('.', ''))
            
            if metri_quadri_numerico > 0:
                return f"{prezzo_numerico // metri_quadri_numerico} €"
        return 'N/A'
    except Exception as e:
        print(f"Errore nel calcolo prezzo/m² per prezzo='{row['Prezzo']}' e metri='{row['Metri Quadri']}': {e}")
        return 'N/A'

async def send_telegram_message(message):
    try:
        for user_id in AUTHORIZED_USERS:
            await bot.send_message(chat_id=user_id, text=message, parse_mode="HTML")
        print("Messaggio inviato agli utenti autorizzati.")
    except Exception as e:
        print(f"Errore durante l'invio del messaggio su Telegram: {e}")

def fetch_data(url):
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il fetch dei dati: {e}")
        return None

def is_valid_listing(item):
    return (
        item['Link'] != 'N/A' and
        'immobiliare.it' in item['Link'] and 
        item['Zona'] not in ZONE_ESCLUSE
    )

def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    
    for item in soup.select(".nd-list__item"):
        title = item.select_one("h2").text.strip() if item.select_one("h2") else "N/A"
        link = item.select_one("a.in-listingCardTitle")["href"] if item.select_one("a.in-listingCardTitle") else "N/A"
        price = item.select_one(".in-listingCardPrice span").text.strip() if item.select_one(".in-listingCardPrice span") else "N/A"
        location_tag = item.select_one("a.in-listingCardTitle.is-spaced, a.in-listingCardTitle")
        location = location_tag.text.strip() if location_tag else "N/A"

        # Usa le nuove funzioni per estrarre indirizzo e zona
        indirizzo = extract_indirizzo(location)
        zona = extract_zona(location)

        nr_locali = "N/A"
        locali_element = item.select_one('use[href="#planimetry"]')
        if locali_element:
            nr_locali_span = locali_element.find_parent("div").select_one("span")
            nr_locali = nr_locali_span.text.strip() if nr_locali_span else "N/A"

        metri_quadri = "N/A"
        metri_element = item.select_one('use[href="#size"]')
        if metri_element:
            metri_span = metri_element.find_parent("div").select_one("span")
            metri_quadri = metri_span.text.strip().replace("m2", "").strip() if metri_span else "N/A"

        listing = {
            "Titolo": title,
            "Prezzo": price,
            "Indirizzo": indirizzo,
            "Zona": zona,
            "Numero Locali": nr_locali,
            "Metri Quadri": metri_quadri,
            "Link": link
        }
        
        if is_valid_listing(listing):
            listings.append(listing)

    print(f"Trovati {len(listings)} annunci validi in questa pagina")
    return listings

async def block_unauthorized_messages(update: Update, context: CallbackContext):
    if str(update.effective_chat.id) not in AUTHORIZED_USERS:
        await update.message.reply_text("Mi dispiace, non sei autorizzato a utilizzare questo bot.")
        return

async def main():
    # Inizializza l'applicazione
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Aggiungi handler per bloccare tutti i messaggi non autorizzati
    app.add_handler(MessageHandler(filters.ALL, block_unauthorized_messages))
    
    # Avvia il polling in background
    await app.initialize()
    await app.start()
    await app.update_queue.put(Update.de_json({'update_id': 0}, app.bot))
    
    print("Avvio scraping...")
    all_listings = []

    # Leggi il file CSV esistente all'inizio
    CSV_FILE = "immobiliare_annunci.csv"
    previous_data = pd.DataFrame()
    if os.path.exists(CSV_FILE):
        try:
            previous_data = pd.read_csv(CSV_FILE)
            previous_data = previous_data.dropna(how='all')
            previous_data = previous_data[previous_data['Link'].str.contains('immobiliare.it', na=False)]
        except Exception as e:
            print(f"Errore nella lettura del CSV: {e}")
            previous_data = pd.DataFrame()

    for page in range(1, 4):###############################################################################################
        print(f"Scraping pagina {page}...")
        url = f"{BASE_URL}&pag={page}"
        html_content = fetch_data(url)
        
        if html_content:
            listings = parse_html(html_content)
            if listings:
                all_listings.extend(listings)
        else:
            print(f"Errore durante il fetch della pagina {page}.")

    if all_listings:
        new_df = pd.DataFrame(all_listings)
        new_df['Prezzo al m2'] = new_df.apply(calcola_prezzo_m2, axis=1)

        if not previous_data.empty:
            new_listings = new_df[~new_df['Link'].isin(previous_data['Link'])]
        else:
            new_listings = new_df

        if not new_listings.empty:
            print(f"Trovati {len(new_listings)} nuovi annunci da inviare.")
            for _, item in new_listings.iterrows():
                message = (
                    f"<b>Zona:</b> {item['Zona']}\n"
                    f"<b>Indirizzo:</b> {item['Indirizzo']}\n"
                    f"<b>Prezzo:</b> {item['Prezzo']}\n"
                    f"<b>Metri²:</b> {item['Metri Quadri']}\n"
                    f"<b>Nr Locali:</b> {item['Numero Locali']}\n"
                    f"<b>Prezzo al m²:</b> <u>{item['Prezzo al m2']}</u>\n"
                    f"<b>Link:</b> <a href=\"{item['Link']}\">Visualizza annuncio</a>"
                )
                await send_telegram_message(message)
        else:
            print("Nessun nuovo annuncio trovato.")

        if not previous_data.empty:
            combined_df = pd.concat([previous_data, new_listings], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['Link'])
        else:
            combined_df = new_df
        
        combined_df = combined_df.dropna(how='all')
        combined_df.to_csv(CSV_FILE, index=False, encoding="utf-8")
        print(f"File CSV aggiornato con successo. Totale annunci: {len(combined_df)}")
    else:
        print("Nessun annuncio valido trovato.")

    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())