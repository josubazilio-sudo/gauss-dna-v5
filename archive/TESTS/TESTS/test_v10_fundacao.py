import sys
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time
import unittest
from datetime import datetime, timezone
from typing import Any

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.skills.skill_opinion import SkillOpinion, SkillMetrics
from ENGINE.skills.base import BaseSkill
from ENGINE.skills.skill_registry import SkillRegistry, SkillRegistration
from ENGINE.skills.skills_engine import SkillsEngine
from ENGINE.memory.operational_memory import OperationalMemory
from ENGINE.memory.institutional_memory import InstitutionalMemory


# ============================================================
# 1. CONTRATOS — SkillOpinion
# ============================================================
class TestSkillOpinion(unittest.TestCase):
    def test_valid_opinion(self):
        o = SkillOpinion(
            skill_name="test", confidence=0.85, risk=0.20, probability=0.75,
            evidence=["BOS confirmado"], observations="analise ok", success=True,
        )
        self.assertEqual(o.skill_name, "test")
        self.assertEqual(o.confidence, 0.85)
        self.assertEqual(o.risk, 0.20)
        self.assertEqual(o.probability, 0.75)
        self.assertEqual(o.evidence, ["BOS confirmado"])
        self.assertTrue(o.success)

    def test_imutavel(self):
        o = SkillOpinion(
            skill_name="test", confidence=0.5, risk=0.3, probability=0.6,
            evidence=["ev1"], observations="obs", success=True,
        )
        with self.assertRaises(Exception):
            o.confidence = 0.9

    def test_confidence_boundaries(self):
        with self.assertRaises(ValueError):
            SkillOpinion(skill_name="t", confidence=1.5, risk=0.0, probability=0.0, evidence=[], observations="", success=True)
        with self.assertRaises(ValueError):
            SkillOpinion(skill_name="t", confidence=-0.1, risk=0.0, probability=0.0, evidence=[], observations="", success=True)
        o = SkillOpinion(skill_name="t", confidence=0.0, risk=0.0, probability=0.0, evidence=[], observations="", success=True)
        self.assertEqual(o.confidence, 0.0)
        o = SkillOpinion(skill_name="t", confidence=1.0, risk=1.0, probability=1.0, evidence=[], observations="", success=True)
        self.assertEqual(o.confidence, 1.0)

    def test_risk_boundaries(self):
        with self.assertRaises(ValueError):
            SkillOpinion(skill_name="t", confidence=0.0, risk=1.5, probability=0.0, evidence=[], observations="", success=True)

    def test_probability_boundaries(self):
        with self.assertRaises(ValueError):
            SkillOpinion(skill_name="t", confidence=0.0, risk=0.0, probability=-0.01, evidence=[], observations="", success=True)

    def test_evidence_list_vazia(self):
        o = SkillOpinion(skill_name="t", confidence=0.5, risk=0.3, probability=0.6, evidence=[], observations="", success=True)
        self.assertEqual(o.evidence, [])

    def test_metrics_default(self):
        o = SkillOpinion(skill_name="t", confidence=0.5, risk=0.3, probability=0.6, evidence=[], observations="", success=True)
        self.assertEqual(o.metrics.availability, 1.0)
        self.assertEqual(o.metrics.recent_errors, 0)

    def test_metrics_custom(self):
        m = SkillMetrics(availability=0.95, avg_latency_ms=150.0, historical_precision=0.72, reliability=0.88, recent_errors=2)
        o = SkillOpinion(skill_name="t", confidence=0.5, risk=0.3, probability=0.6, evidence=[], observations="", success=True, metrics=m)
        self.assertEqual(o.metrics.availability, 0.95)
        self.assertEqual(o.metrics.recent_errors, 2)


# ============================================================
# 2. CONTRATOS — BaseSkill
# ============================================================
class TestBaseSkill(unittest.TestCase):
    def test_nao_pode_instanciar_abc(self):
        with self.assertRaises(TypeError):
            BaseSkill(name="x", version="1.0", category="test")

    def test_subclass_concreta(self):
        class FakeSkill(BaseSkill):
            def analyze(self, market_context, world_model=None):
                return SkillOpinion(
                    skill_name=self.name, confidence=0.5, risk=0.3, probability=0.6,
                    evidence=["teste"], observations="ok", success=True,
                )
        s = FakeSkill(name="test_skill", version="2.0", category="smc")
        self.assertEqual(s.name, "test_skill")
        self.assertEqual(s.version, "2.0")
        self.assertEqual(s.category, "smc")
        o = s.analyze(None)
        self.assertEqual(o.skill_name, "test_skill")


# ============================================================
# 3. CONTRATOS — SkillRegistry
# ============================================================
class TestSkillRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = SkillRegistry()

    def _make_skill(self, name, category="smc", version="1.0"):
        class FakeSkill(BaseSkill):
            def analyze(self, ctx, wm=None):
                return SkillOpinion(skill_name=self.name, confidence=0.5, risk=0.3, probability=0.6, evidence=[], observations="", success=True)
        return FakeSkill(name=name, version=version, category=category)

    def test_registrar_e_obter(self):
        s = self._make_skill("skill_a")
        self.registry.register(s)
        self.assertIs(self.registry.get_skill("skill_a"), s)

    def test_count(self):
        self.registry.register(self._make_skill("a"))
        self.registry.register(self._make_skill("b"))
        self.assertEqual(self.registry.count, 2)

    def test_names(self):
        self.registry.register(self._make_skill("alpha"))
        self.registry.register(self._make_skill("beta"))
        self.assertIn("alpha", self.registry.names)
        self.assertIn("beta", self.registry.names)

    def test_unregister(self):
        s = self._make_skill("remover")
        self.registry.register(s)
        self.registry.unregister("remover")
        self.assertIsNone(self.registry.get_skill("remover"))
        self.assertEqual(self.registry.count, 0)

    def test_get_all_skills(self):
        a = self._make_skill("a")
        b = self._make_skill("b")
        self.registry.register(a)
        self.registry.register(b)
        skills = self.registry.get_all_skills()
        self.assertEqual(len(skills), 2)

    def test_get_skill_inexistente(self):
        self.assertIsNone(self.registry.get_skill("nao_existe"))

    def test_categorias(self):
        a = self._make_skill("trend", category="trend")
        b = self._make_skill("volume", category="volume")
        self.registry.register(a)
        self.registry.register(b)
        trends = self.registry.get_skills_by_category("trend")
        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0].name, "trend")

    def test_duplicidade_sobrescreve(self):
        a = self._make_skill("mesmo_nome", version="1.0")
        b = self._make_skill("mesmo_nome", version="2.0")
        self.registry.register(a)
        self.registry.register(b)
        obtido = self.registry.get_skill("mesmo_nome")
        self.assertEqual(obtido.version, "2.0")

    def test_registration_completo(self):
        s = self._make_skill("completa")
        reg = SkillRegistration(name="completa", category="smc", version="1.0", author="test", capabilities=["bos", "choch"], priority=5)
        self.registry.register(s, reg)
        stored = self.registry.get_registration("completa")
        self.assertEqual(stored.author, "test")
        self.assertEqual(stored.capabilities, ["bos", "choch"])
        self.assertEqual(stored.priority, 5)

    def test_get_all_registrations(self):
        a = self._make_skill("a")
        b = self._make_skill("b")
        self.registry.register(a)
        self.registry.register(b)
        self.assertEqual(len(self.registry.get_all_registrations()), 2)


# ============================================================
# 4. SkillsEngine
# ============================================================
class FakeSkill(BaseSkill):
    def __init__(self, name, delay=0, fail=False):
        super().__init__(name=name, version="1.0", category="test")
        self._delay = delay
        self._fail = fail

    def analyze(self, ctx, wm=None):
        if self._delay:
            time.sleep(self._delay)
        if self._fail:
            raise RuntimeError(f"Skill {self.name} failed")
        return SkillOpinion(
            skill_name=self.name, confidence=0.8, risk=0.2, probability=0.75,
            evidence=[f"{self.name} executou"], observations="ok", success=True,
        )


class TestSkillsEngine(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.engine = SkillsEngine(event_bus=self.bus)

    def test_registro(self):
        s = FakeSkill("s1")
        self.engine.register_skill(s)
        self.assertIs(self.engine.registry.get_skill("s1"), s)

    def test_executar_1_skill(self):
        self.engine.register_skill(FakeSkill("s1"))
        opinions = self.engine.execute_all(None)
        self.assertEqual(len(opinions), 1)
        self.assertEqual(opinions[0].skill_name, "s1")
        self.assertTrue(opinions[0].success)

    def test_executar_10_skills(self):
        for i in range(10):
            self.engine.register_skill(FakeSkill(f"s{i}"))
        opinions = self.engine.execute_all(None)
        self.assertEqual(len(opinions), 10)
        for o in opinions:
            self.assertTrue(o.success)

    def test_executar_50_skills(self):
        for i in range(50):
            self.engine.register_skill(FakeSkill(f"s{i}"))
        opinions = self.engine.execute_all(None)
        self.assertEqual(len(opinions), 50)

    def test_fallback_skill_falha(self):
        self.engine.register_skill(FakeSkill("boa"))
        self.engine.register_skill(FakeSkill("ruim", fail=True))
        opinions = self.engine.execute_all(None)
        for o in opinions:
            if o.skill_name == "ruim":
                self.assertFalse(o.success)
                self.assertEqual(o.confidence, 0.0)
                self.assertEqual(o.risk, 1.0)

    def test_timeout_individual(self):
        self.engine.register_skill(FakeSkill("lenta", delay=0.1))
        opinions = self.engine.execute_all(None, timeout=5)
        self.assertEqual(len(opinions), 1)

    def test_evento_publicado(self):
        received = []
        def handler(event):
            received.append(event)
        self.bus.subscribe("skills.opinions_ready", handler)
        self.engine.register_skill(FakeSkill("s1"))
        self.engine.execute_all(None)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].type, "skills.opinions_ready")
        self.assertEqual(received[0].data["count"], 1)

    def test_nenhuma_skill_registrada(self):
        opinions = self.engine.execute_all(None)
        self.assertEqual(opinions, [])

    def test_registry_property(self):
        self.assertIsNotNone(self.engine.registry)


# ============================================================
# 5. OperationalMemory
# ============================================================
class TestOperationalMemory(unittest.TestCase):
    def setUp(self):
        self.mem = OperationalMemory(max_entries=5)

    def test_set_e_get(self):
        self.mem.set("chave", "valor")
        self.assertEqual(self.mem.get("chave"), "valor")

    def test_get_default(self):
        self.assertEqual(self.mem.get("nao_existe", "padrao"), "padrao")

    def test_exists(self):
        self.mem.set("a", 1)
        self.assertTrue(self.mem.exists("a"))
        self.assertFalse(self.mem.exists("b"))

    def test_remove(self):
        self.mem.set("a", 1)
        self.mem.remove("a")
        self.assertFalse(self.mem.exists("a"))

    def test_clear(self):
        self.mem.set("a", 1)
        self.mem.set("b", 2)
        self.mem.clear()
        self.assertEqual(self.mem.size, 0)

    def test_snapshot(self):
        self.mem.set("a", 1)
        self.mem.set("b", 2)
        snap = self.mem.snapshot()
        self.assertEqual(snap, {"a": 1, "b": 2})

    def test_lru_eviction(self):
        for i in range(10):
            self.mem.set(f"k{i}", i)
        self.assertEqual(self.mem.size, 5)
        self.assertIsNone(self.mem.get("k0"))
        self.assertIsNotNone(self.mem.get("k9"))

    def test_keys(self):
        self.mem.set("a", 1)
        self.mem.set("b", 2)
        self.assertIn("a", self.mem.keys())
        self.assertIn("b", self.mem.keys())

    def test_get_with_timestamp(self):
        self.mem.set("a", 42)
        result = self.mem.get_with_timestamp("a")
        self.assertIsNotNone(result)
        val, ts = result
        self.assertEqual(val, 42)
        self.assertIsInstance(ts, datetime)

    def test_get_with_timestamp_ausente(self):
        self.assertIsNone(self.mem.get_with_timestamp("nao_existe"))


# ============================================================
# 6. InstitutionalMemory
# ============================================================
import tempfile
import os


class TestInstitutionalMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mem = InstitutionalMemory(storage_path=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_store_and_load(self):
        data = {"key": "value", "num": 42}
        h = self.mem.store_decision("test_001", data)
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 16)
        loaded = self.mem.load_decision("test_001")
        self.assertEqual(loaded["key"], "value")
        self.assertEqual(loaded["num"], 42)
        self.assertEqual(loaded["decision_hash"], h)

    def test_list_decisions(self):
        self.mem.store_decision("dec1", {"a": 1})
        self.mem.store_decision("dec2", {"b": 2})
        decs = self.mem.list_decisions()
        self.assertIn("dec1", decs)
        self.assertIn("dec2", decs)

    def test_verify_integrity(self):
        data = {"signal": "BTC LONG", "confidence": 0.85}
        h = self.mem.store_decision("integro", data)
        self.assertTrue(self.mem.verify_decision("integro"))

    def test_verify_corruption(self):
        data = {"signal": "BTC LONG"}
        self.mem.store_decision("corrupto", data)
        filepath = os.path.join(self.tmpdir, "corrupto.json")
        with open(filepath, "r") as f:
            content = f.read()
        content = content.replace("BTC LONG", "ETH SHORT")
        with open(filepath, "w") as f:
            f.write(content)
        self.assertFalse(self.mem.verify_decision("corrupto"))

    def test_load_inexistente(self):
        self.assertIsNone(self.mem.load_decision("nao_existe"))

    def test_delete(self):
        self.mem.store_decision("del", {"x": 1})
        self.assertTrue(self.mem.delete_decision("del"))
        self.assertFalse(self.mem.delete_decision("del"))

    def test_hash_deterministico(self):
        data = {"a": 1, "b": 2}
        h1 = self.mem._compute_hash(data)
        h2 = self.mem._compute_hash(data)
        self.assertEqual(h1, h2)

    def test_hash_diferente_para_dados_diferentes(self):
        h1 = self.mem._compute_hash({"a": 1})
        h2 = self.mem._compute_hash({"a": 2})
        self.assertNotEqual(h1, h2)


# ============================================================
# 7. EventBus + EventTypes AMI-OS
# ============================================================
class TestEventTypesAMI(unittest.TestCase):
    def test_market_data_ready(self):
        self.assertEqual(EventTypes.MARKET_DATA_READY, "market.data_ready")

    def test_world_model_updated(self):
        self.assertEqual(EventTypes.WORLD_MODEL_UPDATED, "world.model_updated")

    def test_skills_opinions_ready(self):
        self.assertEqual(EventTypes.SKILLS_OPINIONS_READY, "skills.opinions_ready")

    def test_council_verdict_ready(self):
        self.assertEqual(EventTypes.COUNCIL_VERDICT_READY, "council.verdict_ready")

    def test_meta_hold(self):
        self.assertEqual(EventTypes.META_HOLD, "meta.hold")

    def test_meta_proceed(self):
        self.assertEqual(EventTypes.META_PROCEED, "meta.proceed")

    def test_decision_made(self):
        self.assertEqual(EventTypes.DECISION_MADE, "decision.made")

    def test_execution_order(self):
        self.assertEqual(EventTypes.EXECUTION_ORDER, "execution.order")

    def test_policy_blocked(self):
        self.assertEqual(EventTypes.POLICY_BLOCKED, "policy.blocked")

    def test_policy_approved(self):
        self.assertEqual(EventTypes.POLICY_APPROVED, "policy.approved")


class TestEventBusAMI(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_subscribe_publish(self):
        received = []
        def handler(event):
            received.append(event)
        self.bus.subscribe("market.data_ready", handler)
        self.bus.publish(Event("market.data_ready", {"pair": "BTCUSDT"}))
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["pair"], "BTCUSDT")

    def test_multiplos_subscribers(self):
        r1, r2 = [], []
        self.bus.subscribe("test.evt", lambda e: r1.append(1))
        self.bus.subscribe("test.evt", lambda e: r2.append(1))
        self.bus.publish(Event("test.evt"))
        self.assertEqual(len(r1), 1)
        self.assertEqual(len(r2), 1)

    def test_unsubscribe(self):
        received = []
        def handler(event):
            received.append(event)
        self.bus.subscribe("test.evt", handler)
        self.bus.unsubscribe("test.evt", handler)
        self.bus.publish(Event("test.evt"))
        self.assertEqual(len(received), 0)

    def test_subscriber_falha_nao_quebra(self):
        def falha(event):
            raise ValueError("erro")
        ok = []
        self.bus.subscribe("test.falha", falha)
        self.bus.subscribe("test.falha", lambda e: ok.append(1))
        self.bus.publish(Event("test.falha"))
        self.assertEqual(len(ok), 1)

    def test_evento_sem_subscriber(self):
        self.bus.publish(Event("evento.sem.ninguem"))

    def test_pipeline_completo_eventos(self):
        events = []
        def collector(e):
            events.append(e.type)
        for t in ["market.data_ready", "world.model_updated", "skills.opinions_ready",
                   "council.verdict_ready", "meta.proceed", "decision.made", "execution.order"]:
            self.bus.subscribe(t, collector)
        for t in ["market.data_ready", "world.model_updated", "skills.opinions_ready",
                   "council.verdict_ready", "meta.proceed", "decision.made", "execution.order"]:
            self.bus.publish(Event(t))
        self.assertEqual(len(events), 7)
        self.assertEqual(events, ["market.data_ready", "world.model_updated", "skills.opinions_ready",
                                   "council.verdict_ready", "meta.proceed", "decision.made", "execution.order"])

    def test_evento_com_timestamp(self):
        before = datetime.now(timezone.utc)
        evt = Event("test.timing")
        after = datetime.now(timezone.utc)
        self.assertIsNotNone(evt.timestamp)
        self.assertTrue(before <= evt.timestamp <= after)


# ============================================================
# 8. STRESS TEST — SkillsEngine
# ============================================================
class StressTestSkillsEngine(unittest.TestCase):
    def test_100_execucoes(self):
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        for i in range(10):
            engine.register_skill(FakeSkill(f"s{i}"))
        for _ in range(10):
            opinions = engine.execute_all(None, timeout=10)
            self.assertEqual(len(opinions), 10)

    def test_1000_execucoes_acumuladas(self):
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        for i in range(10):
            engine.register_skill(FakeSkill(f"s{i}"))
        total = 0
        for _ in range(100):
            opinions = engine.execute_all(None, timeout=10)
            total += len(opinions)
        self.assertEqual(total, 1000)

    def test_stress_10000(self):
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        for i in range(5):
            engine.register_skill(FakeSkill(f"s{i}"))
        total = 0
        for _ in range(2000):
            opinions = engine.execute_all(None, timeout=10)
            total += len(opinions)
        self.assertEqual(total, 10000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
