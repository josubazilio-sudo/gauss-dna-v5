import hashlib
import json
import re
from typing import Dict, List, Set, Tuple, Sequence

from ENGINE.skills.skill_opinion import SkillOpinion
from ENGINE.council.evidence_types import (
    EvidenceNode,
    EvidenceCluster,
    EvidenceConflict,
    EvidenceGraph,
)
from ENGINE.council.evidence_config import (
    TOPIC_MAP,
    TEXT_SIMILARITY_THRESHOLD,
)


STOP_WORDS: Set[str] = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "da", "do", "das", "dos", "no", "na", "nos", "nas",
    "em", "para", "com", "por", "que", "e", "eh", "nao",
    "se", "mais", "mas", "ao", "aos", "a", "as",
    "pelo", "pela", "pelos", "pelas",
    "tem", "tem", "ha", "entre", "com", "uma", "como",
}


class EvidenceGraphBuilder:

    def build(self, opinions: Sequence[SkillOpinion]) -> EvidenceGraph:
        if not opinions:
            return EvidenceGraph(
                nodes=(), clusters=(), contradictions=(),
                confidence=0.0, quality=0.0, consistency=0.0,
                graph_hash=self._compute_hash([], [], []),
                num_skills=0, num_duplicates_removed=0,
            )

        nodes, duplicates = self._build_nodes(opinions)
        clusters = self._build_clusters(nodes)
        contradictions = self._build_contradictions(nodes)
        confidence = self._compute_confidence(nodes)
        quality = self._compute_quality(nodes, len(opinions), duplicates)
        consistency = self._compute_consistency(contradictions, len(nodes))
        graph_hash = self._compute_hash(nodes, clusters, contradictions)

        return EvidenceGraph(
            nodes=nodes,
            clusters=clusters,
            contradictions=contradictions,
            confidence=confidence,
            quality=quality,
            consistency=consistency,
            graph_hash=graph_hash,
            num_skills=len(opinions),
            num_duplicates_removed=duplicates,
        )

    def _normalize_text(self, text: str) -> str:
        return text.lower().strip()

    def _tokenize(self, text: str) -> Set[str]:
        text = text.lower()
        tokens = set(re.findall(r"\b[a-záéíóúãõç0-9]+\b", text))
        return tokens - STOP_WORDS

    def _jaccard_similarity(self, a: Set[str], b: Set[str]) -> float:
        if not a or not b:
            return 0.0
        intersection = a & b
        union = a | b
        return len(intersection) / len(union) if union else 0.0

    def _infer_topic(self, text: str) -> str:
        tokens = self._tokenize(text)
        for token in tokens:
            if token in TOPIC_MAP:
                return TOPIC_MAP[token]
        return "Geral"

    def _build_nodes(self, opinions: Sequence[SkillOpinion]) -> Tuple[Tuple[EvidenceNode, ...], int]:
        merged: Dict[str, Dict] = {}
        duplicates = 0

        for opinion in opinions:
            for evidence_text in opinion.evidence:
                key = self._normalize_text(evidence_text)
                if key in merged:
                    entry = merged[key]
                    if opinion.skill_name not in entry["skills"]:
                        entry["skills"].append(opinion.skill_name)
                        entry["occurrences"] += 1
                        entry["confidences"].append(opinion.confidence)
                        entry["risks"].append(opinion.risk)
                        entry["probs"].append(opinion.probability)
                        duplicates += 1
                else:
                    merged[key] = {
                        "text": evidence_text,
                        "skills": [opinion.skill_name],
                        "occurrences": 1,
                        "confidences": [opinion.confidence],
                        "risks": [opinion.risk],
                        "probs": [opinion.probability],
                    }

        nodes: List[EvidenceNode] = []
        for idx, (norm_key, entry) in enumerate(merged.items()):
            n = len(entry["confidences"])
            avg_conf = sum(entry["confidences"]) / n
            avg_risk = sum(entry["risks"]) / n
            avg_prob = sum(entry["probs"]) / n
            occ = entry["occurrences"]
            weight = min(1.0, 0.5 + occ * 0.1)

            nodes.append(EvidenceNode(
                id=f"ev_{idx}",
                evidence_text=entry["text"],
                source_skills=tuple(sorted(entry["skills"])),
                confidence=round(avg_conf, 4),
                risk=round(avg_risk, 4),
                probability=round(avg_prob, 4),
                occurrences=occ,
                weight=round(weight, 4),
            ))

        return tuple(nodes), duplicates

    def _build_clusters(self, nodes: Tuple[EvidenceNode, ...]) -> Tuple[EvidenceCluster, ...]:
        if len(nodes) < 2:
            return ()

        adj: Dict[str, Set[str]] = {n.id: set() for n in nodes}

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                node_a = nodes[i]
                node_b = nodes[j]
                tokens_a = self._tokenize(node_a.evidence_text)
                tokens_b = self._tokenize(node_b.evidence_text)
                similarity = self._jaccard_similarity(tokens_a, tokens_b)
                if similarity >= TEXT_SIMILARITY_THRESHOLD:
                    adj[node_a.id].add(node_b.id)
                    adj[node_b.id].add(node_a.id)

        node_map = {n.id: n for n in nodes}
        visited: Set[str] = set()
        clusters: List[EvidenceCluster] = []
        cluster_id = 0

        for node in nodes:
            if node.id in visited:
                continue
            component: List[str] = []
            stack = [node.id]
            while stack:
                curr = stack.pop()
                if curr in visited:
                    continue
                visited.add(curr)
                component.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        stack.append(neighbor)
            if len(component) < 2:
                continue

            texts = [node_map[nid].evidence_text for nid in component]
            all_tokens: Set[str] = set()
            for nid in component:
                all_tokens |= self._tokenize(node_map[nid].evidence_text)

            confs = [node_map[nid].confidence for nid in component]
            mean_conf = sum(confs) / len(confs)
            weight_sum = sum(node_map[nid].weight for nid in component)
            cluster_conf = round(mean_conf * min(1.0, 1.0 + weight_sum * 0.05), 4)

            topic = self._infer_topic(" ".join(texts))

            internal_sims = []
            for x in range(len(component)):
                for y in range(x + 1, len(component)):
                    tx = self._tokenize(node_map[component[x]].evidence_text)
                    ty = self._tokenize(node_map[component[y]].evidence_text)
                    internal_sims.append(self._jaccard_similarity(tx, ty))
            consist = round(sum(internal_sims) / len(internal_sims), 4) if internal_sims else 1.0

            clusters.append(EvidenceCluster(
                id=f"cluster_{cluster_id}",
                topic=topic,
                node_ids=tuple(component),
                evidence_texts=tuple(texts),
                confidence=cluster_conf,
                consistency=consist,
                weight=round(weight_sum / len(component), 4),
            ))
            cluster_id += 1

        return tuple(clusters)

    def _build_contradictions(self, nodes: Tuple[EvidenceNode, ...]) -> Tuple[EvidenceConflict, ...]:
        if len(nodes) < 2:
            return ()

        contradictions: List[EvidenceConflict] = []

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                node_a = nodes[i]
                node_b = nodes[j]
                tokens_a = self._tokenize(node_a.evidence_text)
                tokens_b = self._tokenize(node_b.evidence_text)
                similarity = self._jaccard_similarity(tokens_a, tokens_b)

                conf_a_high = node_a.confidence > 0.5
                conf_b_high = node_b.confidence > 0.5
                confidence_opposed = conf_a_high != conf_b_high

                if not confidence_opposed:
                    continue

                severity = round(abs(node_a.confidence - node_b.confidence) * similarity, 4) if similarity > 0 else round(abs(node_a.confidence - node_b.confidence) * 0.3, 4)
                severity = min(severity, 1.0)

                if severity < 0.05:
                    continue

                contradictions.append(EvidenceConflict(
                    source_id=node_a.id,
                    target_id=node_b.id,
                    severity=severity,
                    description=(
                        f"Conflito entre {node_a.source_skills} (conf={node_a.confidence}) "
                        f"e {node_b.source_skills} (conf={node_b.confidence})"
                    ),
                ))

        return tuple(contradictions)

    @staticmethod
    def _compute_confidence(nodes: Tuple[EvidenceNode, ...]) -> float:
        if not nodes:
            return 0.0
        weighted = sum(n.confidence * n.weight for n in nodes)
        total_weight = sum(n.weight for n in nodes)
        if total_weight == 0:
            return 0.0
        return round(weighted / total_weight, 4)

    @staticmethod
    def _compute_quality(nodes: Tuple[EvidenceNode, ...], num_skills: int, duplicates: int) -> float:
        if not nodes or num_skills == 0:
            return 0.0
        source_div = min(1.0, len({s for n in nodes for s in n.source_skills}) / num_skills)
        conf_factor = sum(n.confidence for n in nodes) / len(nodes)
        weight_factor = sum(n.weight for n in nodes) / len(nodes)
        quality = round(0.4 * source_div + 0.35 * conf_factor + 0.25 * weight_factor, 4)
        return quality

    @staticmethod
    def _compute_consistency(contradictions: Tuple[EvidenceConflict, ...], num_nodes: int) -> float:
        if num_nodes == 0:
            return 0.0
        if not contradictions:
            return 1.0
        total_severity = sum(c.severity for c in contradictions)
        max_possible = num_nodes * 0.5
        penalty = min(1.0, total_severity / max_possible) if max_possible > 0 else 0.0
        return round(1.0 - penalty, 4)

    @staticmethod
    def _compute_hash(
        nodes: Tuple[EvidenceNode, ...],
        clusters: Tuple[EvidenceCluster, ...],
        contradictions: Tuple[EvidenceConflict, ...],
    ) -> str:
        canonical: List[str] = []
        for n in sorted(nodes, key=lambda x: x.evidence_text):
            canonical.append(f"NODE|{n.evidence_text}|{n.confidence}|{n.occurrences}")
        for c in sorted(clusters, key=lambda x: x.id):
            canonical.append(f"CLUS|{c.topic}|{c.confidence}|{c.consistency}")
        for c in sorted(contradictions, key=lambda x: f"{x.source_id}-{x.target_id}"):
            canonical.append(f"CONF|{c.source_id}|{c.target_id}|{c.severity}")
        raw = "||".join(canonical)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
