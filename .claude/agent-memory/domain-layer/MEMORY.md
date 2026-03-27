# Domain Layer Agent Memory

## Project Structure
- Frontend: `robo-analyzer-vue3/` (Vue 3 + Pinia + Cytoscape.js)
- Domain Layer Backend: `domain-layer/` (Python FastAPI)
- API Gateway: `api-gateway/` (Spring Boot)
- Ontology store: `domain-layer/app/services/schema_store.py` (Neo4j-backed)

## Key Frontend Files - Ontology Management
- `robo-analyzer-vue3/src/components/domain/MultiLayerOntologyViewer.vue` - Main ontology viewer with Cytoscape graph (very large file, ~13K+ lines)
- `robo-analyzer-vue3/src/stores/ontology.ts` - Pinia store for ontology state
- `robo-analyzer-vue3/src/components/ontology/OntologyTab.vue` - Alternative ontology tab (wizard-based)
- `robo-analyzer-vue3/src/components/ontology/SchemaSelector.vue` - Schema dropdown selector
- `robo-analyzer-vue3/src/services/api.ts` - API service layer

## Known Patterns
- MultiLayerOntologyViewer uses Cytoscape.js (`let cy: cytoscape.Core`) for graph visualization
- Save endpoint: POST `/api/gateway/ontology/schema` -> `domain-layer/app/routers/ontology.py`
- Schema store uses Neo4j for persistence with in-memory active schema tracking

## Bug Fix: Save causing blank screen (2026-03)
- Root cause: `v-if="loading"` / `v-else` in MultiLayerOntologyViewer destroyed Cytoscape DOM during save
- Fix: Changed to `v-show` to preserve DOM and Cytoscape instance during loading transitions
- Location: Lines ~260-267 in MultiLayerOntologyViewer.vue
