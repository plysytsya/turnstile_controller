#!/bin/bash

# Script de configuración para ODROID - Turnstile Controller
# Ejecutar directamente en el ODROID después de conectarse vía SSH

ROJO='\033[0;31m'
VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
AZUL='\033[0;34m'
NC='\033[0m'
SUDO_PASS=""

mostrar_banner() {
    clear
    echo -e "${AZUL}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           CONFIGURACIÓN DE ODROID - TURNSTILE              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

validar_sudo() {
    echo -e "${AMARILLO}Ingrese su contraseña de sudo:${NC}"
    read -s SUDO_PASS
    echo ""
    echo "$SUDO_PASS" | sudo -S -v 2>/dev/null
    if [ $? -ne 0 ]; then
        echo -e "${ROJO}Contraseña incorrecta. Saliendo...${NC}"
        exit 1
    fi
    echo -e "${VERDE}Contraseña validada.${NC}"
    echo ""
}

ejecutar_sudo() {
    echo "$SUDO_PASS" | sudo -S "$@" 2>/dev/null
}

mostrar_menu() {
    echo -e "${VERDE}Seleccione una opción:${NC}"
    echo ""
    echo "  [0] Configurar WiFi"
    echo "  [1] Configurar SSH remoto"
    echo "  [2] Configurar control de acceso"
    echo ""
    echo "  [q] Salir"
    echo ""
    echo -e "${AMARILLO}Opción: ${NC}"
}

configurar_wifi() {
    mostrar_banner
    echo -e "${AZUL}══════════════ CONFIGURACIÓN DE WIFI ══════════════${NC}"
    echo ""
    echo -e "${AMARILLO}Escaneando redes WiFi...${NC}"
    echo ""
    echo -e "${VERDE}Redes disponibles:${NC}"
    echo "────────────────────────────────────────────────────"
    ejecutar_sudo nmcli device wifi list
    echo "────────────────────────────────────────────────────"
    echo ""
    echo -e "${AMARILLO}Nombre de la red (SSID):${NC}"
    read WIFI_SSID
    if [ -z "$WIFI_SSID" ]; then
        echo -e "${ROJO}Error: SSID vacío.${NC}"
        read -p "Presione Enter..."
        return
    fi
    echo -e "${AMARILLO}Contraseña de la red:${NC}"
    read WIFI_PASS
    echo ""
    if [ -z "$WIFI_PASS" ]; then
        echo -e "${ROJO}Error: Contraseña vacía.${NC}"
        read -p "Presione Enter..."
        return
    fi
    echo ""
    echo -e "${AMARILLO}Conectando a \"$WIFI_SSID\"...${NC}"
    echo ""
    RESULTADO=$(ejecutar_sudo nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASS" 2>&1)
    echo -e "${VERDE}Resultado:${NC}"
    echo "────────────────────────────────────────────────────"
    echo "$RESULTADO"
    echo "────────────────────────────────────────────────────"
    echo ""
    read -p "Presione Enter..."
}

configurar_ssh() {
    mostrar_banner
    echo -e "${AZUL}══════════════ CONFIGURACIÓN SSH ══════════════${NC}"
    echo ""
    echo "  [1] Ver estado SSH"
    echo "  [2] Habilitar SSH"
    echo "  [3] Deshabilitar SSH"
    echo "  [4] Reiniciar SSH"
    echo "  [5] Mostrar IP"
    echo "  [0] Volver"
    echo ""
    echo -e "${AMARILLO}Opción: ${NC}"
    read OPC
    case $OPC in
        1) echo ""; ejecutar_sudo systemctl status ssh --no-pager ;;
        2) ejecutar_sudo systemctl enable ssh; ejecutar_sudo systemctl start ssh; echo -e "${VERDE}SSH habilitado.${NC}" ;;
        3) ejecutar_sudo systemctl stop ssh; ejecutar_sudo systemctl disable ssh; echo -e "${VERDE}SSH deshabilitado.${NC}" ;;
        4) ejecutar_sudo systemctl restart ssh; echo -e "${VERDE}SSH reiniciado.${NC}" ;;
        5) echo ""; ip -4 addr show | grep -E "inet " | awk '{print $2, $NF}' ;;
        0) return ;;
        *) echo -e "${ROJO}Opción inválida.${NC}" ;;
    esac
    echo ""
    read -p "Presione Enter..."
    configurar_ssh
}

configurar_control_acceso() {
    mostrar_banner
    echo -e "${AZUL}══════════════ CONTROL DE ACCESO ══════════════${NC}"
    echo ""
    echo "  [1] Ver estado del servicio"
    echo "  [2] Iniciar servicio"
    echo "  [3] Detener servicio"
    echo "  [4] Reiniciar servicio"
    echo "  [5] Ver logs"
    echo "  [6] Editar configuración"
    echo "  [0] Volver"
    echo ""
    echo -e "${AMARILLO}Opción: ${NC}"
    read OPC
    case $OPC in
        1) ejecutar_sudo systemctl status turnstile --no-pager 2>/dev/null || echo "Servicio no encontrado" ;;
        2) ejecutar_sudo systemctl start turnstile 2>/dev/null && echo -e "${VERDE}Iniciado.${NC}" || echo -e "${ROJO}Error.${NC}" ;;
        3) ejecutar_sudo systemctl stop turnstile 2>/dev/null && echo -e "${VERDE}Detenido.${NC}" || echo -e "${ROJO}Error.${NC}" ;;
        4) ejecutar_sudo systemctl restart turnstile 2>/dev/null && echo -e "${VERDE}Reiniciado.${NC}" || echo -e "${ROJO}Error.${NC}" ;;
        5) ejecutar_sudo journalctl -u turnstile -n 50 --no-pager 2>/dev/null || echo "Sin logs" ;;
        6) CONFIG="/home/manager/turnstile_controller/config.json"; [ -f "$CONFIG" ] && ejecutar_sudo nano "$CONFIG" || echo -e "${ROJO}Config no encontrada.${NC}" ;;
        0) return ;;
        *) echo -e "${ROJO}Opción inválida.${NC}" ;;
    esac
    echo ""
    read -p "Presione Enter..."
    configurar_control_acceso
}

# PROGRAMA PRINCIPAL
mostrar_banner
validar_sudo

while true; do
    mostrar_banner
    mostrar_menu
    read OPCION
    case $OPCION in
        0) configurar_wifi ;;
        1) configurar_ssh ;;
        2) configurar_control_acceso ;;
        q|Q) echo -e "${VERDE}¡Hasta luego!${NC}"; exit 0 ;;
        *) echo -e "${ROJO}Opción inválida.${NC}"; sleep 1 ;;
    esac
done
