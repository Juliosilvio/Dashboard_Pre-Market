import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Porta 5173 e fixa de proposito: e a mesma que api_server.py libera no CORS
// (allow_origin_regex, ver api_server.py 1.19.0). Se mudar aqui, muda la
// tambem.
//
// host: true (2026-09-27, pedido do usuario - compartilhar com colega via
// Tailscale/VPN): por padrao o Vite so aceita conexao vinda do proprio PC
// (bind em localhost); com host: true ele escuta em todas as interfaces
// de rede (0.0.0.0), entao um PC de fora na mesma VPN tambem consegue
// abrir http://<ip-tailscale-do-Julio>:5173. Sem isso, o navegador do
// colega dava ERR_CONNECTION_REFUSED mesmo com a VPN certa.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
