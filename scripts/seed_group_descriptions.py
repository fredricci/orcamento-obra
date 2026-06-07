"""
Script para atualizar descrições dos grupos e renomear Fechadura Digital → Projeto.
Rodar: python scripts/seed_group_descriptions.py
"""

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings

GRUPOS = [
    ("Obra Civil",            "Mão de obra de pedreiros, demolição, alvenaria, reboco, contrapiso, estrutura e serviços gerais de construção"),
    ("Limpeza",               "Limpeza por obra"),
    ("Ar Condicionado",       "Compra e instalação de aparelhos de ar condicionado, manutenção e infraestrutura de instalação"),
    ("Iluminação Técnica",    "Luminárias de teto, spots, trilhos de LED, iluminação funcional dos ambientes"),
    ("Iluminação Decorativa", "Arandelas, pendentes, abajures"),
    ("Acabamentos Elétricos", "Tomadas, interruptores, espelhos, quadro de distribuição, fiação e instalação elétrica"),
    ("Louças e Metais",       "Vasos sanitários, cubas, pias, torneiras, chuveiros, misturadores e acessórios de banheiro e cozinha, porta toalhas"),
    ("Piso Porcelanato",      "Compra de porcelanato, rejunte e materiais relacionados"),
    ("Revestimento",          "Azulejos, cerâmica de parede, revestimento de banheiro, cozinha e áreas molhadas"),
    ("Piso de Madeira",       "Piso laminado, vinílico, assoalho ou parquet, instalação"),
    ("Marcenaria",            "Móveis planejados, armários, cozinha, closet, estantes e bancadas sob medida"),
    ("Aquecedor a Gás",       "Aquecedor de passagem a gás, instalação, tubulação de gás e registro"),
    ("Fechamento Varanda",    "Fechamento de varanda com vidro, esquadrias ou estrutura metálica"),
    ("Vidraçaria",            "Espelhos, box de banheiro, portas de vidro, vidros temperados, janelas de vidro"),
    ("Acessórios",            "Cabides, porta-toalhas, papeleiros, saboneteiras e acessórios de banheiro e cozinha"),
    ("Churrasqueira",         "Churrasqueira, estrutura, revestimento e equipamentos relacionados"),
    ("Automação",             "Automação residencial, fechaduras inteligentes, câmeras, sensores e sistemas de controle, materiais de automação"),
    ("Chopeira",              "Chopeira residencial, instalação e acessórios"),
    ("Eletrodomésticos",      "Fogão, forno, geladeira, lava-louças, máquina de lavar e outros eletrodomésticos"),
    ("Mobílias",              "Sofás, camas, mesas, cadeiras, estantes e demais móveis soltos"),
    ("Cortinas",              "Cortinas, persianas, blackout, trilhos e instalação"),
    ("Decoração",             "Quadros, tapetes, plantas, objetos decorativos e itens de acabamento visual"),
    ("Varal",                 "Varal interno ou externo, estrutura e instalação"),
    # Fechadura Digital renomeado para Projeto
    ("Projeto",               "Custos com arquitetos, projetos, ART, etc"),
]


async def main():
    from app.models.group import Group  # noqa

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        # Renomear Fechadura Digital → Projeto (se ainda existir)
        stmt = select(Group).where(Group.name == "Fechadura Digital")
        result = await db.execute(stmt)
        fd = result.scalar_one_or_none()
        if fd:
            fd.name = "Projeto"
            fd.description = "Custos com arquitetos, projetos, ART, etc"
            print("✓ Renomeado: Fechadura Digital → Projeto")

        # Atualizar descrições dos demais grupos
        for nome, descricao in GRUPOS:
            if nome == "Projeto" and fd:
                continue  # já tratado acima
            stmt = select(Group).where(Group.name == nome)
            result = await db.execute(stmt)
            group = result.scalar_one_or_none()
            if group:
                group.description = descricao
                print(f"✓ Atualizado: {nome}")
            else:
                print(f"⚠ Não encontrado: {nome}")

        await db.commit()
        print("\nConcluído!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
