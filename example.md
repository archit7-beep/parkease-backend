```mermaid
graph TD
Dataset --> Datastore
Datastore --> WeatherDataset
WeatherDataset --> ARModel
ARModel --> GraphLAM
GraphLAM --> Prediction
```
