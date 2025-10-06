"""
Sistema di Generazione FAQ con LLM
Protocollo completo per creare FAQ strutturate e validate
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import json


class ComplessitaLivello(Enum):
    CITTADINO = "cittadino"
    PROFESSIONISTA = "professionista"
    ESPERTO = "esperto"


class TargetAudience(Enum):
    CITTADINI = "cittadini"
    PROFESSIONISTI = "professionisti"
    IMPRESE = "imprese"
    ENTI_PUBBLICI = "enti_pubblici"


@dataclass
class ContestoFAQ:
    """Definisce il contesto per la generazione della FAQ"""
    area_tematica: str
    target: TargetAudience
    livello_complessita: ComplessitaLivello
    normative_riferimento: List[str]
    parole_chiave: List[str]
    casi_pratici: Optional[List[str]] = None


@dataclass
class FAQ:
    """Struttura dati per una FAQ"""
    id: str
    domanda: str
    risposta: str
    area_tematica: str
    target: str
    riferimenti_normativi: List[str]
    parole_chiave: List[str]
    data_creazione: str
    data_aggiornamento: str
    validata: bool = False
    score_qualita: Optional[float] = None


class FAQGeneratorLLM:
    """
    Sistema principale per la generazione di FAQ con LLM
    """

    def __init__(self, llm_client, validation_rules: Dict = None):
        """
        Args:
            llm_client: Client per il modello LLM (es. OpenAI, Anthropic)
            validation_rules: Regole di validazione personalizzate
        """
        self.llm = llm_client
        self.validation_rules = validation_rules or self._default_validation_rules()

    def _default_validation_rules(self) -> Dict:
        """Regole di validazione di default"""
        return {
            "min_lunghezza_domanda": 10,
            "max_lunghezza_domanda": 200,
            "min_lunghezza_risposta": 50,
            "max_lunghezza_risposta": 2000,
            "richiedi_riferimenti": True,
            "evita_linguaggio_colloquiale": True
        }

    # ==================== FASE 1: RACCOLTA E ANALISI ====================

    def analizza_contesto(self, documenti: List[str],
                          domande_frequenti: List[str]) -> Dict:
        """
        Fase 1.1: Analizza il contesto documentale e identifica gap informativi

        Args:
            documenti: Lista di documenti normativi/tecnici
            domande_frequenti: Domande ricorrenti degli utenti

        Returns:
            Analisi strutturata del contesto
        """

        prompt_analisi = f"""
Analizza i seguenti documenti e le domande frequenti degli utenti.

DOCUMENTI NORMATIVI:
{self._format_documenti(documenti)}

DOMANDE FREQUENTI DEGLI UTENTI:
{self._format_domande(domande_frequenti)}

Esegui un'analisi strutturata e fornisci:
1. Temi principali identificati
2. Gap informativi (domande senza risposta chiara)
3. Aree di confusione ricorrenti
4. Suggerimenti per nuove FAQ necessarie
5. Livello di complessità richiesto per ogni tema

Formato output: JSON
"""

        response = self.llm.generate(prompt_analisi)
        return json.loads(response)

    # ==================== FASE 2: GENERAZIONE STRUTTURATA ====================

    def genera_faq(self, contesto: ContestoFAQ,
                   domanda_utente: Optional[str] = None) -> FAQ:
        """
        Fase 2.1: Genera una FAQ strutturata basata sul contesto

        Args:
            contesto: Contesto definito per la FAQ
            domanda_utente: Domanda specifica da cui partire (opzionale)

        Returns:
            FAQ generata
        """

        prompt_generazione = self._crea_prompt_generazione(contesto, domanda_utente)

        response = self.llm.generate(
            prompt_generazione,
            temperature=0.3,  # Bassa per consistenza
            max_tokens=1500
        )

        faq_data = self._parse_response(response)

        faq = FAQ(
            id=self._genera_id(),
            domanda=faq_data['domanda'],
            risposta=faq_data['risposta'],
            area_tematica=contesto.area_tematica,
            target=contesto.target.value,
            riferimenti_normativi=faq_data['riferimenti'],
            parole_chiave=contesto.parole_chiave,
            data_creazione=self._get_timestamp(),
            data_aggiornamento=self._get_timestamp()
        )

        return faq

    def _crea_prompt_generazione(self, contesto: ContestoFAQ,
                                 domanda: Optional[str]) -> str:
        """Crea il prompt ottimizzato per la generazione"""

        base_prompt = f"""
Sei un esperto in comunicazione istituzionale dell'Agenzia delle Entrate italiana.

CONTESTO:
- Area tematica: {contesto.area_tematica}
- Target audience: {contesto.target.value}
- Livello di complessità: {contesto.livello_complessita.value}
- Normative di riferimento: {', '.join(contesto.normative_riferimento)}

ISTRUZIONI:
Genera una FAQ chiara, precisa e autorevole seguendo questi criteri:

1. STRUTTURA DELLA DOMANDA:
   - Formulata come la farebbe un utente reale
   - Chiara e specifica
   - Contiene parole chiave: {', '.join(contesto.parole_chiave)}
   - Lunghezza: 10-200 caratteri

2. STRUTTURA DELLA RISPOSTA:
   - Inizia con una risposta diretta (Sì/No se applicabile)
   - Fornisci spiegazione dettagliata
   - Includi riferimenti normativi precisi
   - Usa linguaggio appropriato per il target: {contesto.target.value}
   - Lunghezza: 50-2000 caratteri
   - Se necessario, organizza in paragrafi brevi

3. RIFERIMENTI NORMATIVI:
   - Cita articoli di legge specifici
   - Indica circolari e provvedimenti pertinenti
   - Formato: "Art. X del D.L. n. Y del AAAA"

4. TONE OF VOICE:
   - Formale ma accessibile
   - Autorevole e preciso
   - Evita gergalismi
   - Usa terminologia tecnica solo se necessaria

"""

        if domanda:
            base_prompt += f"\nDOMANDA UTENTE DA ELABORARE:\n{domanda}\n"
        else:
            base_prompt += "\nGenera una domanda frequente rilevante per questo contesto.\n"

        if contesto.casi_pratici:
            base_prompt += f"\nCASI PRATICI DI RIFERIMENTO:\n"
            for caso in contesto.casi_pratici:
                base_prompt += f"- {caso}\n"

        base_prompt += """
OUTPUT RICHIESTO (formato JSON):
{
    "domanda": "La domanda formulata",
    "risposta": "La risposta completa e strutturata",
    "riferimenti": ["Art. X del...", "Circolare n. Y..."],
    "note_tecniche": "Eventuali note per revisione umana"
}
"""

        return base_prompt

    # ==================== FASE 3: VALIDAZIONE MULTI-LIVELLO ====================

    def valida_faq(self, faq: FAQ) -> Dict[str, any]:
        """
        Fase 3.1: Validazione strutturale della FAQ

        Returns:
            Dizionario con risultati validazione
        """

        risultati = {
            "valida": True,
            "errori": [],
            "warning": [],
            "score": 0.0
        }

        # Validazione lunghezze
        if len(faq.domanda) < self.validation_rules["min_lunghezza_domanda"]:
            risultati["errori"].append("Domanda troppo corta")
            risultati["valida"] = False

        if len(faq.risposta) < self.validation_rules["min_lunghezza_risposta"]:
            risultati["errori"].append("Risposta troppo corta")
            risultati["valida"] = False

        # Validazione riferimenti normativi
        if self.validation_rules["richiedi_riferimenti"] and not faq.riferimenti_normativi:
            risultati["warning"].append("Mancano riferimenti normativi")

        # Calcolo score qualità
        score = self._calcola_quality_score(faq)
        risultati["score"] = score
        faq.score_qualita = score

        return risultati

    def validazione_semantica_llm(self, faq: FAQ, contesto: ContestoFAQ) -> Dict:
        """
        Fase 3.2: Validazione semantica usando LLM
        Verifica coerenza, accuratezza e completezza
        """

        prompt_validazione = f"""
Sei un revisore esperto dell'Agenzia delle Entrate.

VALUTA questa FAQ secondo i seguenti criteri:

DOMANDA: {faq.domanda}
RISPOSTA: {faq.risposta}
RIFERIMENTI: {', '.join(faq.riferimenti_normativi)}

AREA TEMATICA: {faq.area_tematica}
TARGET: {faq.target}

CRITERI DI VALUTAZIONE:
1. Accuratezza normativa (0-10): La risposta è corretta rispetto alle normative?
2. Completezza (0-10): La risposta è esaustiva?
3. Chiarezza (0-10): La risposta è comprensibile per il target?
4. Coerenza (0-10): Domanda e risposta sono coerenti?
5. Riferimenti (0-10): I riferimenti normativi sono pertinenti?

OUTPUT (formato JSON):
{{
    "accuratezza": <score>,
    "completezza": <score>,
    "chiarezza": <score>,
    "coerenza": <score>,
    "riferimenti": <score>,
    "score_totale": <media>,
    "raccomandazioni": ["lista di suggerimenti per migliorare"],
    "approvata": <true/false>
}}
"""

        response = self.llm.generate(prompt_validazione, temperature=0.2)
        return json.loads(response)

    def validazione_cross_reference(self, faq: FAQ,
                                    faq_esistenti: List[FAQ]) -> Dict:
        """
        Fase 3.3: Verifica duplicati e coerenza con FAQ esistenti
        """

        prompt_cross = f"""
Verifica se questa nuova FAQ è duplicata o in conflitto con FAQ esistenti.

NUOVA FAQ:
Domanda: {faq.domanda}
Risposta: {faq.risposta}

FAQ ESISTENTI:
{self._format_faq_esistenti(faq_esistenti)}

ANALIZZA:
1. Esistono FAQ duplicate o molto simili?
2. Ci sono conflitti o contraddizioni?
3. La nuova FAQ aggiunge valore informativo?
4. Suggerimenti per integrazione o sostituzione

OUTPUT (JSON):
{{
    "duplicata": <true/false>,
    "faq_simili": [<lista id>],
    "conflitti": [<lista conflitti>],
    "azione_consigliata": "aggiungi/sostituisci/modifica/unisci",
    "motivazione": "spiegazione"
}}
"""

        response = self.llm.generate(prompt_cross, temperature=0.2)
        return json.loads(response)

    # ==================== FASE 4: ARRICCHIMENTO ====================

    def arricchisci_faq(self, faq: FAQ) -> FAQ:
        """
        Fase 4.1: Arricchisce la FAQ con esempi, casi pratici, link
        """

        prompt_arricchimento = f"""
Arricchisci questa FAQ con elementi aggiuntivi utili.

FAQ ORIGINALE:
Domanda: {faq.domanda}
Risposta: {faq.risposta}

AGGIUNGI (se pertinente):
1. Un esempio pratico concreto
2. Casi limite o eccezioni importanti
3. Link a risorse correlate (es. "Vedi anche FAQ n. X")
4. Note operative o suggerimenti pratici

Mantieni il tono istituzionale e la precisione normativa.

OUTPUT (JSON):
{{
    "risposta_arricchita": "risposta completa con aggiunte",
    "esempi_pratici": ["esempio 1", "esempio 2"],
    "faq_correlate": ["id o titolo"],
    "note_operative": "suggerimenti pratici"
}}
"""

        response = self.llm.generate(prompt_arricchimento, temperature=0.4)
        dati_arricchiti = json.loads(response)

        # Aggiorna la FAQ
        faq.risposta = dati_arricchiti['risposta_arricchita']

        return faq

    def genera_varianti_domanda(self, faq: FAQ, num_varianti: int = 3) -> List[str]:
        """
        Fase 4.2: Genera varianti della domanda per migliorare la ricerca
        """

        prompt_varianti = f"""
Genera {num_varianti} varianti della seguente domanda, mantenendo lo stesso significato.
Le varianti devono riflettere modi diversi in cui un utente potrebbe porre la stessa domanda.

DOMANDA ORIGINALE: {faq.domanda}

OUTPUT (JSON):
{{
    "varianti": ["variante 1", "variante 2", "variante 3"]
}}
"""

        response = self.llm.generate(prompt_varianti, temperature=0.7)
        dati = json.loads(response)
        return dati['varianti']

    # ==================== FASE 5: PUBBLICAZIONE ====================

    def prepara_pubblicazione(self, faq: FAQ,
                              metadata: Dict = None) -> Dict:
        """
        Fase 5.1: Prepara la FAQ per la pubblicazione
        """

        output = {
            "id": faq.id,
            "domanda": faq.domanda,
            "risposta": faq.risposta,
            "area_tematica": faq.area_tematica,
            "target": faq.target,
            "riferimenti_normativi": faq.riferimenti_normativi,
            "parole_chiave": faq.parole_chiave,
            "metadata": {
                "data_creazione": faq.data_creazione,
                "data_aggiornamento": faq.data_aggiornamento,
                "validata": faq.validata,
                "score_qualita": faq.score_qualita,
                **(metadata or {})
            }
        }

        return output

    # ==================== UTILITY METHODS ====================

    def _calcola_quality_score(self, faq: FAQ) -> float:
        """Calcola uno score di qualità basato su vari fattori"""
        score = 0.0

        # Lunghezza appropriata
        if 50 <= len(faq.domanda) <= 150:
            score += 0.2
        if 100 <= len(faq.risposta) <= 1500:
            score += 0.2

        # Presenza riferimenti
        if faq.riferimenti_normativi:
            score += 0.3

        # Presenza parole chiave
        if faq.parole_chiave:
            score += 0.15

        # Struttura
        if any(keyword in faq.risposta.lower() for keyword in ['sì', 'no', 'è possibile', 'non è possibile']):
            score += 0.15

        return round(score, 2)

    def _format_documenti(self, documenti: List[str]) -> str:
        return "\n---\n".join(documenti)

    def _format_domande(self, domande: List[str]) -> str:
        return "\n".join(f"{i + 1}. {d}" for i, d in enumerate(domande))

    def _format_faq_esistenti(self, faqs: List[FAQ]) -> str:
        return "\n---\n".join(
            f"ID: {f.id}\nD: {f.domanda}\nR: {f.risposta[:200]}..."
            for f in faqs[:10]  # Limita a 10 per evitare prompt troppo lunghi
        )

    def _parse_response(self, response: str) -> Dict:
        """Parse della risposta JSON dell'LLM"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback: estrazione manuale
            return {
                "domanda": "",
                "risposta": response,
                "riferimenti": []
            }

    def _genera_id(self) -> str:
        """Genera un ID univoco per la FAQ"""
        import uuid
        return f"FAQ-{uuid.uuid4().hex[:8]}"

    def _get_timestamp(self) -> str:
        """Restituisce timestamp corrente"""
        from datetime import datetime
        return datetime.now().isoformat()


# ==================== WORKFLOW COMPLETO ====================

class FAQWorkflow:
    """
    Orchestratore del workflow completo di generazione FAQ
    """

    def __init__(self, generator: FAQGeneratorLLM):
        self.generator = generator
        self.faq_repository = []

    def workflow_completo(self,
                          contesto: ContestoFAQ,
                          documenti: List[str],
                          domande_utenti: List[str],
                          faq_esistenti: List[FAQ] = None) -> Dict:
        """
        Esegue il workflow completo dalla raccolta alla pubblicazione
        """

        risultati = {
            "successo": False,
            "faq_generata": None,
            "validazione": {},
            "raccomandazioni": []
        }

        print("📋 FASE 1: Analisi contesto...")
        analisi = self.generator.analizza_contesto(documenti, domande_utenti)

        print("🔨 FASE 2: Generazione FAQ...")
        faq = self.generator.genera_faq(contesto)

        print("✅ FASE 3: Validazione...")
        # Validazione strutturale
        val_strutturale = self.generator.valida_faq(faq)
        if not val_strutturale["valida"]:
            risultati["validazione"] = val_strutturale
            return risultati

        # Validazione semantica
        val_semantica = self.generator.validazione_semantica_llm(faq, contesto)
        if not val_semantica.get("approvata", False):
            risultati["raccomandazioni"] = val_semantica.get("raccomandazioni", [])
            risultati["validazione"] = val_semantica
            return risultati

        # Cross-reference
        if faq_esistenti:
            val_cross = self.generator.validazione_cross_reference(faq, faq_esistenti)
            if val_cross.get("duplicata", False):
                risultati["validazione"]["duplicata"] = True
                risultati["raccomandazioni"].append(val_cross.get("motivazione", ""))
                return risultati

        print("✨ FASE 4: Arricchimento...")
        faq = self.generator.arricchisci_faq(faq)
        varianti = self.generator.genera_varianti_domanda(faq)

        print("📤 FASE 5: Preparazione pubblicazione...")
        faq.validata = True
        output = self.generator.prepara_pubblicazione(faq, {
            "varianti_domanda": varianti,
            "analisi_contesto": analisi
        })

        risultati["successo"] = True
        risultati["faq_generata"] = output
        risultati["validazione"] = {
            "strutturale": val_strutturale,
            "semantica": val_semantica
        }

        return risultati


# ==================== ESEMPIO DI UTILIZZO ====================

if __name__ == "__main__":
    # Mock LLM client (sostituisci con client reale)
    class MockLLMClient:
        def generate(self, prompt, **kwargs):
            return '{"domanda": "Esempio domanda?", "risposta": "Esempio risposta", "riferimenti": ["Art. 1"]}'


    # Inizializzazione
    llm_client = MockLLMClient()
    generator = FAQGeneratorLLM(llm_client)
    workflow = FAQWorkflow(generator)

    # Definizione contesto
    contesto = ContestoFAQ(
        area_tematica="Superbonus 110%",
        target=TargetAudience.CITTADINI,
        livello_complessita=ComplessitaLivello.CITTADINO,
        normative_riferimento=[
            "D.L. 34/2020",
            "Circolare 24/E/2020"
        ],
        parole_chiave=["superbonus", "detrazione", "110%", "lavori"],
        casi_pratici=[
            "Condominio con lavori trainanti e trainati",
            "Cessione del credito a banca"
        ]
    )

    # Documenti e domande
    documenti = [
        "Articolo 119 del D.L. 34/2020...",
        "Circolare 24/E del 2020..."
    ]

    domande_utenti = [
        "Posso usare il superbonus per il mio appartamento?",
        "Come funziona la cessione del credito?",
        "Quali lavori sono trainanti?"
    ]

    # Esecuzione workflow
    risultato = workflow.workflow_completo(
        contesto=contesto,
        documenti=documenti,
        domande_utenti=domande_utenti
    )

    print("\n" + "=" * 60)
    print("RISULTATO WORKFLOW")
    print("=" * 60)
    print(json.dumps(risultato, indent=2, ensure_ascii=False))