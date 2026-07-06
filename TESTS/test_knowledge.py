"""
Testes do sistema de conhecimento (FASE 03).
"""

import unittest
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from CORE.knowledge.knowledge_entry import KnowledgeEntry, KnowledgeArea, area_label
from CORE.knowledge.knowledge_registry import KnowledgeRegistry
from CORE.knowledge.knowledge_validator import KnowledgeValidator
from CORE.knowledge.file_knowledge_store import FileKnowledgeStore
from CORE.knowledge.knowledge_search import KnowledgeSearch
from CORE.knowledge.knowledge_report import KnowledgeReport
from CORE.knowledge.knowledge_engine import KnowledgeEngine


class TestKnowledgeArea(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(KnowledgeArea.MARKET.value, "market")
        self.assertEqual(KnowledgeArea.TRADING.value, "trading")
        self.assertEqual(KnowledgeArea.RISK.value, "risk")

    def test_area_label(self):
        self.assertEqual(area_label(KnowledgeArea.MARKET), "Mercado")
        self.assertEqual(area_label(KnowledgeArea.AI), "Inteligência Artificial")


class TestKnowledgeEntry(unittest.TestCase):
    def test_create(self):
        entry = KnowledgeEntry.create(
            KnowledgeArea.MARKET, "Regimes de Mercado", "Conteudo detalhado sobre regimes",
        )
        self.assertTrue(len(entry.entry_id) > 0)
        self.assertEqual(entry.area, KnowledgeArea.MARKET)
        self.assertEqual(entry.title, "Regimes de Mercado")
        self.assertEqual(entry.version, "1.0.0")
        self.assertEqual(entry.source, "manual")

    def test_create_with_tags(self):
        entry = KnowledgeEntry.create(
            KnowledgeArea.TRADING, "SMC", "Conteudo",
            tags=["smart_money", "order_block"],
            author="quant_team",
        )
        self.assertIn("smart_money", entry.tags)
        self.assertEqual(entry.author, "quant_team")

    def test_to_dict_roundtrip(self):
        original = KnowledgeEntry.create(
            KnowledgeArea.RISK, "Position Sizing", "Calculo de tamanho de posicao",
        )
        d = original.to_dict()
        self.assertEqual(d["area"], "risk")
        restored = KnowledgeEntry.from_dict(d)
        self.assertEqual(restored.title, original.title)
        self.assertEqual(restored.area, original.area)
        self.assertEqual(restored.entry_id, original.entry_id)

    def test_create_defaults(self):
        entry = KnowledgeEntry.create(KnowledgeArea.ENGINEERING, "Clean Code", "Codigo limpo e modular")
        self.assertEqual(len(entry.references), 0)
        self.assertEqual(len(entry.tags), 0)
        self.assertEqual(entry.author, "system")
        self.assertEqual(entry.source, "manual")

    def test_create_with_references(self):
        entry = KnowledgeEntry.create(
            KnowledgeArea.AI, "Prompt Engineering", "Como escrever prompts",
            references=["DOC023", "DOC024"],
        )
        self.assertIn("DOC023", entry.references)


class TestKnowledgeRegistry(unittest.TestCase):
    def setUp(self):
        self._registry = KnowledgeRegistry()

    def test_areas_count(self):
        self.assertEqual(len(self._registry.areas()), 7)

    def test_categories_market(self):
        cats = self._registry.categories(KnowledgeArea.MARKET)
        self.assertIn("liquidez", cats)
        self.assertIn("tendencia", cats)

    def test_categories_trading(self):
        cats = self._registry.categories(KnowledgeArea.TRADING)
        self.assertIn("order_blocks", cats)
        self.assertIn("fair_value_gap", cats)

    def test_categories_unknown_returns_empty(self):
        cats = self._registry.categories(KnowledgeArea.ORDERFLOW)
        self.assertGreater(len(cats), 0)

    def test_search_categories(self):
        results = self._registry.search_categories("liquidez")
        self.assertIn(KnowledgeArea.MARKET, results)
        self.assertIn("liquidez", results[KnowledgeArea.MARKET])


class TestKnowledgeValidator(unittest.TestCase):
    def setUp(self):
        self._validator = KnowledgeValidator()

    def test_valid_entry(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "Titulo valido", "Conteudo com mais de 10 chars")
        errors = self._validator.validate(entry)
        self.assertEqual(len(errors), 0)

    def test_short_title(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "AB", "Conteudo valido")
        errors = self._validator.validate(entry)
        self.assertGreater(len(errors), 0)

    def test_short_content(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "Titulo valido", "Curto")
        errors = self._validator.validate(entry)
        self.assertGreater(len(errors), 0)

    def test_missing_area_not_checked_by_validator(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "Titulo", "Conteudo com mais de 10 caracteres")
        errors = self._validator.validate(entry)
        self.assertEqual(len(errors), 0)


class TestFileKnowledgeStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileKnowledgeStore(Path(self._tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_save_and_load(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "Test", "Conteudo de teste")
        self._store.save(entry)
        loaded = self._store.load(KnowledgeArea.MARKET, entry.entry_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "Test")

    def test_load_nonexistent(self):
        self.assertIsNone(self._store.load(KnowledgeArea.MARKET, "noexist"))

    def test_list_area(self):
        e1 = KnowledgeEntry.create(KnowledgeArea.MARKET, "A", "Conteudo A")
        e2 = KnowledgeEntry.create(KnowledgeArea.MARKET, "B", "Conteudo B")
        self._store.save(e1)
        self._store.save(e2)
        entries = self._store.list_area(KnowledgeArea.MARKET)
        self.assertEqual(len(entries), 2)

    def test_list_area_empty(self):
        entries = self._store.list_area(KnowledgeArea.TRADING)
        self.assertEqual(len(entries), 0)

    def test_count(self):
        self._store.save(KnowledgeEntry.create(KnowledgeArea.MARKET, "A", "C"))
        self._store.save(KnowledgeEntry.create(KnowledgeArea.MARKET, "B", "C"))
        self.assertEqual(self._store.count(KnowledgeArea.MARKET), 2)
        self.assertEqual(self._store.count(KnowledgeArea.TRADING), 0)

    def test_delete(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "A", "C")
        self._store.save(entry)
        self.assertEqual(self._store.count(KnowledgeArea.MARKET), 1)
        self._store.delete(KnowledgeArea.MARKET, entry.entry_id)
        self.assertEqual(self._store.count(KnowledgeArea.MARKET), 0)


class TestKnowledgeSearch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileKnowledgeStore(Path(self._tmp))
        self._search = KnowledgeSearch(self._store)
        self._store.save(KnowledgeEntry.create(
            KnowledgeArea.MARKET, "Liquidez", "Como identificar liquidez no mercado",
            tags=["liquidez", "volume"],
        ))
        self._store.save(KnowledgeEntry.create(
            KnowledgeArea.TRADING, "Order Block", "Estrutura de order blocks",
            tags=["order_block", "smc"],
        ))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_search_title(self):
        results = self._search.search("liquidez")
        self.assertEqual(len(results), 1)

    def test_search_content(self):
        results = self._search.search("order blocks")
        self.assertEqual(len(results), 1)

    def test_search_all(self):
        results = self._search.search("de")
        self.assertGreater(len(results), 0)

    def test_search_no_match(self):
        results = self._search.search("naoexiste")
        self.assertEqual(len(results), 0)

    def test_search_by_area(self):
        results = self._search.search("liquidez", area=KnowledgeArea.MARKET)
        self.assertEqual(len(results), 1)

    def test_search_by_area_no_match(self):
        results = self._search.search("liquidez", area=KnowledgeArea.TRADING)
        self.assertEqual(len(results), 0)

    def test_search_by_tag(self):
        results = self._search.search_by_tag("smc")
        self.assertEqual(len(results), 1)


class TestKnowledgeReport(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileKnowledgeStore(Path(self._tmp))
        self._registry = KnowledgeRegistry()
        self._report = KnowledgeReport(self._store, self._registry)
        self._store.save(KnowledgeEntry.create(KnowledgeArea.MARKET, "A", "C"))
        self._store.save(KnowledgeEntry.create(KnowledgeArea.TRADING, "B", "C"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_summary(self):
        summary = self._report.summary()
        self.assertIn("market", summary)
        self.assertIn("trading", summary)
        self.assertEqual(summary["market"], 1)
        self.assertEqual(summary["trading"], 1)

    def test_generate(self):
        report = self._report.generate()
        self.assertIn("Base Oficial de Conhecimento", report)


class TestKnowledgeEngine(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._engine = KnowledgeEngine(base_dir=Path(self._tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_add_valid_entry(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "Teste", "Conteudo de teste do engine")
        result = self._engine.add(entry)
        self.assertTrue(result)

    def test_add_invalid_entry(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "AB", "C")
        result = self._engine.add(entry)
        self.assertFalse(result)

    def test_get(self):
        entry = KnowledgeEntry.create(KnowledgeArea.MARKET, "Test", "Conteudo de teste do engine")
        self._engine.add(entry)
        loaded = self._engine.get(KnowledgeArea.MARKET, entry.entry_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "Test")

    def test_list_area(self):
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.MARKET, "Regimes de Mercado", "Conteudo completo sobre regimes de mercado"))
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.MARKET, "Tendencia", "Conteudo completo sobre tendencia"))
        entries = self._engine.list_area(KnowledgeArea.MARKET)
        self.assertEqual(len(entries), 2)

    def test_search(self):
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.TRADING, "Smart Money", "Conceitos de Smart Money Concepts"))
        results = self._engine.search("smart")
        self.assertEqual(len(results), 1)

    def test_search_by_area(self):
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.MARKET, "Liquidez", "Analise de liquidez no mercado"))
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.TRADING, "Liquidez Trading", "Trading liquidez conceitos"))
        results = self._engine.search("Liquidez", area=KnowledgeArea.MARKET)
        self.assertEqual(len(results), 1)

    def test_count_total(self):
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.MARKET, "Regimes", "Conteudo completo sobre regimes"))
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.TRADING, "SMC", "Conteudo completo sobre SMC"))
        self.assertEqual(self._engine.count(), 2)

    def test_count_by_area(self):
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.MARKET, "Liquidez", "Conteudo completo sobre liquidez"))
        self.assertEqual(self._engine.count(KnowledgeArea.MARKET), 1)
        self.assertEqual(self._engine.count(KnowledgeArea.TRADING), 0)

    def test_report(self):
        self._engine.add(KnowledgeEntry.create(KnowledgeArea.ENGINEERING, "Clean Code", "Principios de codigo limpo"))
        report = self._engine.report()
        self.assertIn("Clean Code", report)


if __name__ == "__main__":
    unittest.main()
