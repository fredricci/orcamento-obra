"""
Script de importação do orçamento previsto a partir da planilha Google Sheets.
Rodar: python scripts/importar_previsto.py

Mapeamentos aplicados:
- MARMORARIA         → Pedras
- LIMPEZA PÓS OBRA  → Limpeza
- VIDROS             → Vidraçaria
- PORTA DETERGENTE   → Louças e Metais
- "ideoa"            → ideia (typo corrigido)
- Valor vazio        → 0.01 (placeholder)
- Mobília: fornecedor vira descrição (itens sem descrição)
"""

import asyncio
import re
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.budget_item import BudgetItem, ItemStatus, Priority
from app.models.group import Group

# ── Dados da planilha ────────────────────────────────────────────────────────
DADOS = [
    ("OBRA CIVIL",               "FABRICA ENGENHARIA",      "OBRA CIVIL CONFORME ESCOPO NO ORÇAMENTO *sem instalação ar condicionado / sem limpeza pós obra", "alta",  "orcado",     "165000.00"),
    ("LIMPEZA PÓS OBRA",         "L4 LIMPEZAS",             "LIMPEZA PESADA PÓS OBRA PROFISSIONAL",                                                             "alta",  "orcado",     "5000.00"),
    ("AR CONDICIONADO",          "CLIMASOL",                "EQUIPAMENTOS DE AR CONDICIONADO (equipamentos e instalação)",                                        "alta",  "ideia",      "70000.00"),
    ("ILUMINAÇÃO TÉCNICA",       "LABLUZ",                  "PEÇAS DE ILUMINAÇÃO TÉCNICA (instalação inclusa no escopo da obra civil)",                          "alta",  "ideia",      "30000.00"),
    ("ILUMINAÇÃO DECORATIVA",    "BOOBAM",                  "PEÇAS DE ILUMINAÇÃO DECORATIVAS",                                                                   "baixa", "ideia",      "5000.00"),
    ("LOUÇAS E METAIS",          "OBRA FÁCIL / DEXCO",      "CUBA COZINHA, TANQUE, SIFÃO, CHUVEIROS, TORNEIRAS E MISTURADORES E ACESSÓRIOS EM GERAL",           "alta",  "ideia",      "50000.00"),
    ("MARMORARIA",               "TOP WORK MARMORARIA",     "BANCADAS COZINHA, VARANDA GOURMET, LAVANDERIA, BANHOS E LAVABO + BAGUETES E TENTOS",               "alta",  "ideia",      "50000.00"),
    ("PISO PORCELANATO",         "PORTOBELLO SHOP",         "PISO PORCELANATO TRAVERTINO 90X90",                                                                 "alta",  "orcado",     "31886.21"),
    ("REVESTIMENTO",             "PORTOBELLO SHOP",         "PISO E PAREDES EM REVESTIMENTO GIVENGY - Banho Master",                                             "alta",  "orcado",     "8477.43"),
    ("REVESTIMENTO",             "COLORMIX",                "PAREDES EM REVESTIMENTO CERÂMICO VERDE FOCUS AGAVE AC 10X20 - Banho Luca",                         "alta",  "orcado",     "1220.16"),
    ("REVESTIMENTO",             "COLORMIX",                "PAREDES EM REVESTIMENTO CERÂMICO OFF-WHITE FOCUS SHELL AC 10X20 - Banho Hóspede",                  "alta",  "orcado",     "1186.66"),
    ("REVESTIMENTO",             "PORTOBELLO SHOP",         "PORCELANATO AETERNA BIANCO CESELLATO 45X120 - Lavabo",                                              "alta",  "orcado",     "3305.80"),
    ("PISO DE MADEIRA",          "INTERFLOOR",              "PISO DE MADEIRA ÁREA ÍNTIMA",                                                                       "alta",  "ideia",      "16127.79"),
    ("MARCENARIA",               "NOGUEIRAS MARCENARIA",    "MARCENARIA GERAL",                                                                                  "alta",  "ideia",      "200000.00"),
    ("AQUECEDOR A GÁS",          "RINNAI",                  "AQUECEDOR A GÁS 32L + INSTALAÇÃO",                                                                  "alta",  "ideia",      "6150.00"),
    ("FECHAMENTO VARANDA",       "ORIENT VIDROS",           "FECHAMENTO DE VIDRO VARANDA / LAVANDERIA / AQUÁRIO PARA CONDENSADORA",                              "alta",  "ideia",      "25000.00"),
    ("VIDROS",                   "ORIENT VIDROS",           "BOX BANHO LUCCA / BOX BANHO OFFICE",                                                                "alta",  "ideia",      "3360.00"),
    ("VIDROS",                   "CANADA",                  "ESPELHO BRONZE HALL SOCIAL",                                                                        "media", "ideia",      "3567.00"),
    ("VIDROS",                   "ARTFER SERRALHERIA",      "BOX BANHO CASAL / PORTA VIDRO COZINHA",                                                             "alta",  "ideia",      "8495.00"),
    ("ACESSÓRIOS",               "BOOBAM",                  "ESPELHO DECORATIVO LAVABO",                                                                         "media", "ideia",      "2200.00"),
    ("MARCENARIA",               "BRAX",                    "PUXADORES",                                                                                         "alta",  "ideia",      "1836.00"),
    ("CHURRASQUEIRA",            "CAIXA DE ACO",            "CHURRASQUEIRA + COIFA PRETA",                                                                       "alta",  "ideia",      "7000.00"),
    ("AUTOMACAO",                "SOUNDLESS",               "AUDIO VIDEO, INTERNET, ILUMINACAO",                                                                 "alta",  "orcado",     "65000.00"),
    ("CHOPEIRA",                 "",                        "CHOPEIRA",                                                                                          "baixa", "ideia",      "12000.00"),
    ("eletrodomesticos",         "SITES",                   "TV FRAME 55",                                                                                       "alta",  "ideia",      "4500.00"),
    ("eletrodomesticos",         "",                        "TV SALA 98",                                                                                        "media", "ideia",      "20000.00"),
    ("eletrodomesticos",         "",                        "MAQUINA DE GELO IPOMAC",                                                                            "media", "ideia",      "8000.00"),
    ("eletrodomesticos",         "",                        "COIFA COZINHA",                                                                                     "alta",  "ideia",      "4700.00"),
    ("eletrodomesticos",         "",                        "FORNO 80L",                                                                                         "media", "ideia",      "3000.00"),
    ("eletrodomesticos",         "",                        "FOGAO",                                                                                             "alta",  "ideia",      "2000.00"),
    ("eletrodomesticos",         "",                        "LAVA LOUCA",                                                                                        "baixa", "ideia",      "3200.00"),
    ("eletrodomesticos",         "",                        "GELADEIRA",                                                                                         "alta",  "ideia",      "6500.00"),
    ("eletrodomesticos",         "",                        "2 BEBEDORES",                                                                                       "media", "ideia",      "1200.00"),
    # Mobília — fornecedor vira descrição
    ("mobilia",                  "",                        "1 BANQUETA",                                                                                        "media", "ideia",      "1000.00"),
    ("mobilia",                  "",                        "6 CADEIRAS MESA SALA",                                                                              "alta",  "ideia",      "6000.00"),
    ("mobilia",                  "",                        "4 BANQUETAS GOURMET",                                                                               "media", "ideia",      "9200.00"),
    ("mobilia",                  "",                        "PUFF/CADEIRA MAQUIAGEM",                                                                            "media", "ideia",      "800.00"),
    ("mobilia",                  "",                        "1 CADEIRA LUCA",                                                                                    "alta",  "ideia",      "500.00"),
    ("mobilia",                  "",                        "1 SOFÁ SALA DE TV",                                                                                 "alta",  "ideia",      "0.01"),
    ("mobilia",                  "",                        "1 SOFÁ SALA LIVING",                                                                                "baixa", "ideia",      "0.01"),
    ("mobilia",                  "",                        "1 POLTRONA SALA LIVING",                                                                            "baixa", "ideia",      "0.01"),
    ("CORTINAS",                 "",                        "CORTINAS",                                                                                          "baixa", "ideia",      "0.01"),
    ("VARAL",                    "",                        "VARAL",                                                                                             "alta",  "ideia",      "0.01"),
    ("PORTA DETERGENTE",         "",                        "2 PORTA DETERGENTE",                                                                                "alta",  "ideia",      "500.00"),
    ("AUTOMACAO",                "INTELBRASS",              "FECHADURA DIGITAL",                                                                                 "alta",  "ideia",      "1500.00"),
]

# ── Mapeamento de grupos (planilha → sistema) ────────────────────────────────
GRUPO_MAP = {
    "OBRA CIVIL":            "Obra Civil",
    "LIMPEZA PÓS OBRA":      "Limpeza",
    "AR CONDICIONADO":       "Ar Condicionado",
    "ILUMINAÇÃO TÉCNICA":    "Iluminação Técnica",
    "ILUMINAÇÃO DECORATIVA": "Iluminação Decorativa",
    "LOUÇAS E METAIS":       "Louças e Metais",
    "MARMORARIA":            "Pedras",
    "PISO PORCELANATO":      "Piso Porcelanato",
    "REVESTIMENTO":          "Revestimento",
    "PISO DE MADEIRA":       "Piso de Madeira",
    "MARCENARIA":            "Marcenaria",
    "AQUECEDOR A GÁS":       "Aquecedor a Gás",
    "FECHAMENTO VARANDA":    "Fechamento Varanda",
    "VIDROS":                "Vidraçaria",
    "ACESSÓRIOS":            "Acessórios",
    "CHURRASQUEIRA":         "Churrasqueira",
    "AUTOMACAO":             "Automação",
    "CHOPEIRA":              "Chopeira",
    "eletrodomesticos":      "Eletrodomésticos",
    "mobilia":               "Mobílias",
    "CORTINAS":              "Cortinas",
    "VARAL":                 "Varal",
    "PORTA DETERGENTE":      "Louças e Metais",
}


async def main() -> None:
    from app.models.group import Group  # noqa

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        # Carrega todos os grupos ativos em memória
        result = await db.execute(select(Group).where(Group.active == True))  # noqa: E712
        grupos = {g.name: g for g in result.scalars().all()}

        criados = 0
        erros = []

        for grupo_raw, fornecedor, descricao, prioridade_raw, status_raw, valor_raw in DADOS:
            # Mapeia grupo
            grupo_nome = GRUPO_MAP.get(grupo_raw, grupo_raw)
            grupo = grupos.get(grupo_nome)
            if not grupo:
                erros.append(f"⚠ Grupo não encontrado: '{grupo_nome}' (original: '{grupo_raw}')")
                continue

            # Normaliza prioridade
            prioridade_raw = prioridade_raw.strip().lower()
            try:
                prioridade = Priority(prioridade_raw)
            except ValueError:
                erros.append(f"⚠ Prioridade inválida '{prioridade_raw}' — usando 'media'")
                prioridade = Priority.media

            # Normaliza status (corrige typos)
            status_raw = status_raw.strip().lower()
            STATUS_FIX = {"ideoa": "ideia", "ideoia": "ideia", "orçado": "orcado", "contratdo": "contratado"}
            status_raw = STATUS_FIX.get(status_raw, status_raw)
            try:
                status = ItemStatus(status_raw)
            except ValueError:
                erros.append(f"⚠ Status inválido '{status_raw}' — usando 'ideia'")
                status = ItemStatus.ideia

            # Normaliza valor (R$ 1.234,56 → 1234.56)
            # Formato BR: ponto = milhar, vírgula = decimal
            valor_str = valor_raw.strip()
            valor_str = re.sub(r"R\$\s*", "", valor_str).strip()
            if "," in valor_str:
                # Formato BR: remove pontos de milhar, troca vírgula por ponto
                valor_str = valor_str.replace(".", "").replace(",", ".")
            # Se não tem vírgula, pode ser inteiro simples (ex: "500", "1500")
            try:
                valor = Decimal(valor_str) if valor_str else Decimal("0.01")
                if valor <= 0:
                    valor = Decimal("0.01")
            except InvalidOperation:
                valor = Decimal("0.01")

            item = BudgetItem(
                group_id=grupo.id,
                supplier=fornecedor.strip() or None,
                description=descricao.strip() or None,
                priority=prioridade,
                planned_value=valor,
                status=status,
            )
            db.add(item)
            criados += 1
            print(f"✓ {grupo_nome} | {descricao[:50]:<50} | {prioridade.value:<5} | {status.value:<12} | R$ {valor:>12.2f}")

        await db.commit()

    await engine.dispose()

    print(f"\n{'─'*80}")
    print(f"✅ {criados} itens importados com sucesso!")
    if erros:
        print(f"\n⚠ {len(erros)} aviso(s):")
        for e in erros:
            print(f"  {e}")


if __name__ == "__main__":
    asyncio.run(main())
