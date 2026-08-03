// Espelha apps/worker/offer_rules.py (CATEGORY_FAMILY_TERMS/category_family)
// — só para sugerir, ao cadastrar uma palavra-chave no Finder, qual
// categoria da curadoria (/campanhas) ela provavelmente vai acionar depois
// que o motor capturar um produto de verdade. O worker em Python continua
// sendo a única fonte da verdade pro bloqueio real; se as duas listas
// divergirem, o pior caso é a sugestão ficar desatualizada, nunca um
// bloqueio incorreto (mantenha as duas listas em sincronia ao editar).
const CATEGORY_FAMILY_TERMS: { family: string; label: string; terms: string[] }[] = [
  { family: "carregadores", label: "Carregadores", terms: ["carregador", "charger", "charging station", "fonte usb"] },
  { family: "power-banks", label: "Power banks", terms: ["power bank", "bateria externa"] },
  { family: "celulares", label: "Celulares", terms: ["smartphone", "celular", "iphone", "telefone movel"] },
  { family: "monitores", label: "Monitores", terms: ["monitor", "monitores"] },
  { family: "notebooks", label: "Notebooks", terms: ["notebook", "laptop", "macbook"] },
  { family: "tablets", label: "Tablets", terms: ["tablet", "ipad"] },
  { family: "fones", label: "Fones de ouvido", terms: ["fone", "headphone", "headset", "earphone", "earbuds"] },
  { family: "smartwatches", label: "Smartwatches", terms: ["smartwatch", "relogio inteligente"] },
  { family: "televisores", label: "Televisores", terms: ["smart tv", "televisor", "televisao"] },
  { family: "consoles", label: "Consoles", terms: ["playstation", "xbox", "nintendo switch", "console"] },
  { family: "controles", label: "Controles", terms: ["controle gamer", "gamepad", "joystick"] },
  { family: "teclados", label: "Teclados", terms: ["teclado", "keyboard"] },
  { family: "mouses", label: "Mouses", terms: ["mouse"] },
  { family: "ssds", label: "SSDs", terms: ["ssd", "solid state drive"] },
  { family: "placas-mae", label: "Placas-mãe", terms: ["placa mae", "motherboard", "b550", "b450", "x99"] },
  { family: "processadores", label: "Processadores", terms: ["processador", "cpu", "ryzen", "xeon"] },
  { family: "memorias", label: "Memórias RAM", terms: ["memoria ram", "ddr4", "ddr5", "sodimm"] },
  { family: "placas-video", label: "Placas de vídeo", terms: ["placa de video", "gpu", "rtx", "rx 580"] },
  { family: "fontes-pc", label: "Fontes para PC", terms: ["fonte atx", "fonte sfx", "fonte 650w", "power supply"] },
  { family: "refrigeracao-pc", label: "Refrigeração para PC", terms: ["water cooler", "air cooler", "kit fans", "fan argb"] },
  { family: "gabinetes-pc", label: "Gabinetes", terms: ["gabinete", "mini itx", "case pc"] },
  { family: "air-fryers", label: "Air fryers", terms: ["air fryer", "fritadeira eletrica"] },
  { family: "aspiradores", label: "Aspiradores", terms: ["aspirador", "robot vacuum"] },
];

function normalize(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function categoryFamilyForTerm(term: string): { family: string; label: string } | null {
  const padded = ` ${normalize(term)} `;
  for (const entry of CATEGORY_FAMILY_TERMS) {
    if (entry.terms.some((candidate) => padded.includes(` ${normalize(candidate)} `))) {
      return { family: entry.family, label: entry.label };
    }
  }
  return null;
}

// Espelha o fallback de apps/worker/offer_rules.py:category_family quando
// nenhuma família fixa bate: pega o último segmento do caminho de
// categoria da fonte (separado por ">") e normaliza com ESPAÇO (não
// hífen) — é assim que o worker gera a chave "api:<folha>" de verdade.
// Usado só quando o usuário adiciona uma categoria a partir de uma
// sugestão baseada em produto já capturado (products.category real),
// nunca para texto livre digitado à mão.
export function apiFamilyKeyForCategory(category: string): { familyKey: string; label: string } {
  const parts = category
    .split(/\s*>\s*/)
    .map((part) => part.trim())
    .filter(Boolean);
  const leaf = parts[parts.length - 1] || category.trim();
  return { familyKey: `api:${normalize(leaf)}`, label: leaf };
}
