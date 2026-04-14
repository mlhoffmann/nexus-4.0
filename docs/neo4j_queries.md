# NEXUS 4.0 — Queries Neo4j para Demonstração

> Acesse http://localhost:7474 (neo4j / nexus2024) e cole estas queries na barra de comando.
> Cada query mostra uma visão focada e legível do grafo.

---

## 1. Visão por Produto (Supply Chain completo)

### Cadeia do Eixo de Transmissão ET-500
```cypher
MATCH path = (p:Produto {id: 'PROD-001'})-[r]-(connected)
RETURN path
```

### BOM completo com fornecedores (2 hops)
```cypher
MATCH path = (p:Produto {id: 'PROD-001'})-[:USA_MATERIAL]->(m:Material)<-[:FORNECE]-(f:Fornecedor)
RETURN path
```

### Todos os produtos e seus materiais
```cypher
MATCH path = (p:Produto)-[:USA_MATERIAL]->(m:Material)
RETURN path
```

---

## 2. Visão por Equipamento

### CNC-03: tudo que está conectado
```cypher
MATCH path = (e:Equipamento {id: 'CNC-03'})-[*1..2]-(connected)
RETURN path
```

### Sensores monitorando equipamentos
```cypher
MATCH path = (s:Sensor)-[:MONITORA]->(e:Equipamento)
RETURN path
```

### Equipamentos com NCRs abertas
```cypher
MATCH path = (ncr:NCR)-[:ORIGINADA_EM]->(e:Equipamento)
WHERE ncr.status <> 'corrigida'
RETURN path
```

---

## 3. Visão de Fornecedores

### Quem fornece o quê
```cypher
MATCH path = (f:Fornecedor)-[:FORNECE]->(m:Material)
RETURN path
```

### Fornecedores de um material específico (Sensor de Posição)
```cypher
MATCH path = (f:Fornecedor)-[r:FORNECE]->(m:Material {id: 'MP-002'})
RETURN f.nome AS Fornecedor, r.preco AS Preco, r.lead_time AS LeadTime, 
       f.rating AS Rating, f.confiabilidade AS Confiabilidade
ORDER BY f.rating DESC
```

### Fornecedores com pedidos de compra ativos
```cypher
MATCH path = (pc:PedidoCompra)-[:COMPRADO_DE]->(f:Fornecedor)
MATCH (pc)-[:COMPRA_MATERIAL]->(m:Material)
RETURN path
```

---

## 4. Visão de Qualidade

### NCRs e seus produtos afetados
```cypher
MATCH path = (ncr:NCR)-[:AFETA_PRODUTO]->(p:Produto)
RETURN path
```

### NCRs abertas com rastreabilidade (produto + equipamento)
```cypher
MATCH (ncr:NCR)-[:AFETA_PRODUTO]->(p:Produto)
OPTIONAL MATCH (ncr)-[:ORIGINADA_EM]->(e:Equipamento)
WHERE ncr.status <> 'corrigida'
RETURN ncr.id AS NCR, ncr.tipo AS Tipo, ncr.severidade AS Severidade,
       ncr.causa_raiz AS Causa, p.nome AS Produto, e.nome AS Equipamento
```

---

## 5. Análise de Impacto

### Se a CNC-03 falhar, qual o impacto em cascata?
```cypher
MATCH (e:Equipamento {id: 'CNC-03'})-[:PRODUZ]->(p:Produto)
OPTIONAL MATCH (p)<-[:PRODUZ_PRODUTO]-(op:OrdemProducao)
OPTIONAL MATCH (p)-[:USA_MATERIAL]->(m:Material)
OPTIONAL MATCH (ncr:NCR)-[:ORIGINADA_EM]->(e)
RETURN e.nome AS Equipamento, collect(DISTINCT p.nome) AS ProdutosAfetados,
       collect(DISTINCT op.id) AS OrdensImpactadas,
       collect(DISTINCT m.nome) AS MateriaisRelacionados,
       collect(DISTINCT ncr.id) AS NCRsRelacionadas
```

### Materiais críticos e quem os fornece
```cypher
MATCH (m:Material)<-[:FORNECE]-(f:Fornecedor)
WHERE m.estoque < m.estoque_min
RETURN m.nome AS Material, m.estoque AS Estoque, m.estoque_min AS Minimo,
       collect(f.nome) AS Fornecedores
```

### Cadeia completa: Fornecedor → Material → Produto → Equipamento
```cypher
MATCH path = (f:Fornecedor)-[:FORNECE]->(m:Material)<-[:USA_MATERIAL]-(p:Produto)<-[:PRODUZ]-(e:Equipamento)
RETURN path
```

---

## 6. Métricas do Grafo

### Contagem de entidades
```cypher
MATCH (n)
RETURN labels(n)[0] AS Tipo, COUNT(*) AS Total
ORDER BY Total DESC
```

### Contagem de relações
```cypher
MATCH ()-[r]->()
RETURN type(r) AS Relacao, COUNT(*) AS Total
ORDER BY Total DESC
```

### Entidades mais conectadas (hubs)
```cypher
MATCH (n)-[r]-()
RETURN labels(n)[0] AS Tipo, n.nome AS Nome, n.id AS ID, COUNT(r) AS Conexoes
ORDER BY Conexoes DESC
LIMIT 10
```

---

## 7. Queries para Aula (demonstração passo a passo)

### Passo 1: Mostrar apenas produtos
```cypher
MATCH (p:Produto) RETURN p
```

### Passo 2: Adicionar materiais
```cypher
MATCH path = (p:Produto)-[:USA_MATERIAL]->(m:Material)
RETURN path
```

### Passo 3: Adicionar fornecedores
```cypher
MATCH path = (p:Produto)-[:USA_MATERIAL]->(m:Material)<-[:FORNECE]-(f:Fornecedor)
RETURN path
```

### Passo 4: Adicionar equipamentos
```cypher
MATCH p1 = (prod:Produto)-[:USA_MATERIAL]->(m:Material)<-[:FORNECE]-(f:Fornecedor)
MATCH p2 = (e:Equipamento)-[:PRODUZ]->(prod)
RETURN p1, p2
```

### Passo 5: Adicionar NCRs e sensores
```cypher
MATCH p1 = (prod:Produto)-[:USA_MATERIAL]->(m:Material)<-[:FORNECE]-(f:Fornecedor)
MATCH p2 = (e:Equipamento)-[:PRODUZ]->(prod)
OPTIONAL MATCH p3 = (ncr:NCR)-[:AFETA_PRODUTO]->(prod)
OPTIONAL MATCH p4 = (s:Sensor)-[:MONITORA]->(e)
RETURN p1, p2, p3, p4
```
