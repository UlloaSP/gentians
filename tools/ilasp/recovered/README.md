# ASP recuperado de ILASP 4.4.1

Código emitido por el ejecutable ILASP de Mark Law mediante `-st`, conservado
literalmente los días 15 y 16 de octubre de 2026.

El [generador independiente](../standalone/README.md) compila ahora el bias de
otros `.las` y decodifica sus modelos, usando este ASP sin llamar a ILASP.

- [search-space.lp](search-space.lp): metaprograma común de generación y poda,
  desde el marcador `%% General bias constraints.`; 241 líneas.
- [heuristics.lp](heuristics.lp): bloque adicional emitido con
  `--learn-heuristics`; se añade al encoding predeterminado cuando se activa.
- [coin-bias.lp](coin-bias.lp): modes compilados y límites de la tarea `coin`;
  30 líneas.
- [coin-generator.lp](coin-generator.lp): salida original completa para `coin`;
  271 líneas, idéntica a concatenar los dos archivos anteriores.

El fragmento común coincide byte a byte con el emitido para `grandparent` con
las mismas opciones de ejecución. Incluye selección de formas de regla,
seguridad, límites, negación por defecto y ambos bloques de saturación.

Para ejecutar el generador completo:

```powershell
uv run python -m clingo tools/ilasp/recovered/coin-generator.lp 0 --project=show
```

También se pueden pasar `coin-bias.lp` y `search-space.lp` como dos archivos.
El resultado son las 59 representaciones de cláusula distintas verificadas
contra `ILASP -s`, incluidos sus costes tras la decodificación.

El SHA-256 del ejecutable de origen es
`816edec521b48f88bd078960e6b4a1c99723e1f64ea20a502eebd496d89dc6c5`.
El de `coin-generator.lp` es
`d35d367d492ceba31680c60d72dbfcfb36ff488f57fbdc95cd07c0c781326dcd`.

Alcance, validación y límites: [informe de ingeniería inversa](../../../docs/ilasp-reverse-engineering.md).
