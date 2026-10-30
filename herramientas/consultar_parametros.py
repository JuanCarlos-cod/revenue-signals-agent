#!/usr/bin/env python3
"""Herramienta local ficticia. Uso: python herramientas/consultar_parametros.py 'Credito Flexible' Web rate_input"""
import json,sys
from pathlib import Path
if len(sys.argv)!=4:
 print(json.dumps({"error":"uso: consultar_parametros.py PRODUCTO CANAL PARAMETRO"},ensure_ascii=False));sys.exit(2)
producto,canal,parametro=sys.argv[1:]
records=json.loads((Path(__file__).parent/'parametros_simulados.json').read_text(encoding='utf-8'))
found=[r for r in records if r['producto'].casefold()==producto.casefold() and r['canal'].casefold()==canal.casefold() and r['parametro'].casefold()==parametro.casefold()]
print(json.dumps({"consulta":{"producto":producto,"canal":canal,"parametro":parametro},"encontrado":bool(found),"registros":found,"advertencia":"Registro simulado; contrastar con fuentes y no inferir leakage cuantificado"},ensure_ascii=False))
