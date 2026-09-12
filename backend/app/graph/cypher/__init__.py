"""
Parameterised openCypher queries executed against CognoDB / Neo4j.

Preserved and extended from Dependency Detective (Charmi Reddy).
Every dynamic value is supplied as a ``$parameter`` by the caller — no string
concatenation ever reaches the database. Relationship-type whitelists must be
literals in Cypher (types and variable-length bounds cannot be parameters), so
they are fixed here.
"""

# --- Search -----------------------------------------------------------------

# Find components by name substring, optionally restricted to one type label.
SEARCH_COMPONENTS = """
MATCH (n:Component)
WHERE ($q = '' OR toLower(n.name) CONTAINS toLower($q))
  AND ($typeLabel = '' OR $typeLabel IN labels(n))
RETURN n{.*} AS component,
       [l IN labels(n) WHERE l <> 'Component'][0] AS type
ORDER BY n.name
LIMIT $limit
"""

# --- Component lookup ---------------------------------------------------------

# One component plus its owning team (if any).
GET_COMPONENT = """
MATCH (n:Component {id: $id})
OPTIONAL MATCH (n)-[:OWNED_BY]->(t:Team)
RETURN n{.*} AS component,
       [l IN labels(n) WHERE l <> 'Component'][0] AS type,
       t.name AS owner
"""

# --- Direct relationships ------------------------------------------------------

# Everything this component directly relies on (outgoing, excluding ownership).
DIRECT_DEPENDENCIES = """
MATCH (n:Component {id: $id})-[r]->(m:Component)
RETURN type(r) AS rel,
       m{.*} AS component,
       [l IN labels(m) WHERE l <> 'Component'][0] AS type
ORDER BY rel, component.name
"""

# Everything that directly relies on this component (incoming).
DIRECT_DEPENDENTS = """
MATCH (m:Component)-[r]->(n:Component {id: $id})
RETURN type(r) AS rel,
       m{.*} AS component,
       [l IN labels(m) WHERE l <> 'Component'][0] AS type
ORDER BY component.name
"""

# --- Multi-hop impact analysis --------------------------------------------------

# Headline traversal query: every component that can reach $id through 1..6 dependency
# hops, with its hop distance and one shortest chain back to the root
IMPACT_ANALYSIS = """
MATCH (root:Component {id: $id})
MATCH p = (affected:Component)
          -[:DEPENDS_ON|CALLS|READS_FROM|WRITES_TO|USES|DEPLOYED_ON|IMPORTS*1..6]->(root)
WITH affected, min(length(p)) AS depth
MATCH sp = (affected)
           -[:DEPENDS_ON|CALLS|READS_FROM|WRITES_TO|USES|DEPLOYED_ON|IMPORTS*1..6]->(root)
WHERE length(sp) = depth
WITH affected, depth, collect(sp)[0] AS chain
RETURN affected{.*} AS component,
       [l IN labels(affected) WHERE l <> 'Component'][0] AS type,
       depth,
       [n IN nodes(chain) | {id: n.id, name: n.name,
                             type: [l IN labels(n) WHERE l <> 'Component'][0]}] AS chain_nodes,
       [r IN relationships(chain) | type(r)] AS chain_rels
ORDER BY depth, component.name
"""

# --- Dependency paths -------------------------------------------------------------

# All dependency chains between two components (bounded at 8 hops), shortest first
DEPENDENCY_PATHS = """
MATCH (a:Component {id: $fromId}), (b:Component {id: $toId})
MATCH p = (a)-[:DEPENDS_ON|CALLS|READS_FROM|WRITES_TO|USES|DEPLOYED_ON|IMPORTS*1..8]->(b)
RETURN [n IN nodes(p) | {id: n.id, name: n.name,
                         type: [l IN labels(n) WHERE l <> 'Component'][0]}] AS nodes,
       [r IN relationships(p) | type(r)] AS rels
ORDER BY length(p) ASC
LIMIT $maxPaths
"""

# --- Criticality -------------------------------------------------------------------

# Direct and indirect dependent counts for one component. Indirect counts only
# nodes at depth >= 2 so the buckets are disjoint and total = direct + indirect
# matches the impact analysis exactly.
CRITICALITY = """
MATCH (c:Component {id: $id})
OPTIONAL MATCH (d:Component)-[:DEPENDS_ON|CALLS|READS_FROM|WRITES_TO|USES|DEPLOYED_ON|IMPORTS]->(c)
WITH count(DISTINCT d) AS direct
OPTIONAL MATCH (x:Component)-[:DEPENDS_ON|CALLS|READS_FROM|WRITES_TO|USES|DEPLOYED_ON|IMPORTS*2..6]->(c)
RETURN direct, count(DISTINCT x) AS indirect
"""

# Leaderboard: blast-radius of every component, ranked.
CRITICALITY_LEADERBOARD = """
MATCH (c:Component)
OPTIONAL MATCH (x:Component)-[:DEPENDS_ON|CALLS|READS_FROM|WRITES_TO|USES|DEPLOYED_ON|IMPORTS*1..6]->(c)
WITH c, count(DISTINCT x) AS reach
RETURN c{.*} AS component,
       [l IN labels(c) WHERE l <> 'Component'][0] AS type,
       reach
ORDER BY reach DESC, component.name
LIMIT $limit
"""

# --- Stats ---------------------------------------------------------------------------

NODE_COUNT_BY_TYPE = """
MATCH (n:Component)
WITH [l IN labels(n) WHERE l <> 'Component'][0] AS type
RETURN type, count(*) AS count
ORDER BY count DESC
"""

REL_COUNT_BY_TYPE = """
MATCH ()-[r]->()
RETURN type(r) AS type, count(*) AS count
ORDER BY count DESC
"""

TEAM_COUNT = "MATCH (t:Team) RETURN count(t) AS count"

HEALTH_CHECK = "RETURN 1 AS ok"

# --- Schema Extension Queries (Module 4 & 5 additions) -------------------------------

GET_FINDINGS_FOR_COMPONENT = """
MATCH (c:Component {id: $id})-[:FLAGGED_BY]->(f:Finding)
RETURN f{.*} AS finding
ORDER BY f.severity DESC
"""

GET_ALL_FINDINGS = """
MATCH (f:Finding)
OPTIONAL MATCH (c:Component)-[:FLAGGED_BY]->(f)
RETURN f{.*} AS finding, c.id AS component_id, c.name AS component_name
ORDER BY f.severity DESC
"""

GET_INTERNAL_MODULE_GRAPH = """
MATCH (m1:Module)-[r:IMPORTS]->(m2:Module)
RETURN m1{.*} AS source, m2{.*} AS target
LIMIT $limit
"""
