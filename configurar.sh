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
    echo "  [1] Configurar SSH remoto (FRP)"
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
    echo -e "${AZUL}══════════════ CONFIGURACIÓN SSH REMOTO (FRP) ══════════════${NC}"
    echo ""

    # Cargar variables de entorno y activar venv
    SCRIPT_DIR="/home/manager/turnstile_controller"
    if [ -f "$SCRIPT_DIR/.env" ]; then
        set -a
        source "$SCRIPT_DIR/.env"
        set +a
    else
        echo -e "${ROJO}Error: No se encontró el archivo .env${NC}"
        read -p "Presione Enter..."
        return
    fi

    if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
        source "$SCRIPT_DIR/venv/bin/activate"
    else
        echo -e "${ROJO}Error: No se encontró el virtualenv${NC}"
        read -p "Presione Enter..."
        return
    fi

    # Obtener puertos existentes
    echo -e "${AMARILLO}Obteniendo puertos existentes de Notion...${NC}"
    PUERTOS_EXISTENTES=$("$SCRIPT_DIR/notion_hosts.py" list-ports 2>/dev/null)

    if [ $? -ne 0 ]; then
        echo -e "${ROJO}Error al obtener puertos de Notion.${NC}"
        read -p "Presione Enter..."
        return
    fi

    echo -e "${VERDE}Puertos ya asignados:${NC}"
    echo "────────────────────────────────────────────────────"
    echo "$PUERTOS_EXISTENTES"
    echo "────────────────────────────────────────────────────"
    echo ""

    # Generar puerto aleatorio que no exista (rango 6000-6999)
    while true; do
        NUEVO_PUERTO=$((6000 + RANDOM % 1000))
        if ! echo "$PUERTOS_EXISTENTES" | grep -q "^${NUEVO_PUERTO}$"; then
            break
        fi
    done

    echo -e "${VERDE}Puerto generado automáticamente: ${NUEVO_PUERTO}${NC}"
    echo ""

    # Solicitar datos con valores por defecto
    echo -e "${AMARILLO}Nombre (solo letras y números, sin espacios):${NC}"
    read NOMBRE

    # Validar nombre
    if [ -z "$NOMBRE" ]; then
        echo -e "${ROJO}Error: El nombre no puede estar vacío.${NC}"
        read -p "Presione Enter..."
        return
    fi

    if ! [[ "$NOMBRE" =~ ^[a-zA-Z0-9]+$ ]]; then
        echo -e "${ROJO}Error: El nombre solo puede contener letras y números.${NC}"
        read -p "Presione Enter..."
        return
    fi

    echo -e "${AMARILLO}Usuario [manager]:${NC}"
    read USUARIO
    USUARIO=${USUARIO:-manager}

    echo -e "${AMARILLO}Hostname [188.245.164.175]:${NC}"
    read HOSTNAME_FRP
    HOSTNAME_FRP=${HOSTNAME_FRP:-188.245.164.175}

    echo -e "${AMARILLO}Puerto [${NUEVO_PUERTO}]:${NC}"
    read PUERTO_INPUT
    PUERTO=${PUERTO_INPUT:-$NUEVO_PUERTO}

    echo ""
    echo -e "${VERDE}Resumen de configuración:${NC}"
    echo "────────────────────────────────────────────────────"
    echo "  Nombre:   $NOMBRE"
    echo "  Usuario:  $USUARIO"
    echo "  Hostname: $HOSTNAME_FRP"
    echo "  Puerto:   $PUERTO"
    echo "────────────────────────────────────────────────────"
    echo ""
    echo -e "${AMARILLO}¿Confirmar configuración? (s/n):${NC}"
    read CONFIRMAR

    if [[ ! "$CONFIRMAR" =~ ^[sS]$ ]]; then
        echo -e "${AMARILLO}Configuración cancelada.${NC}"
        read -p "Presione Enter..."
        return
    fi

    # Actualizar /etc/frpc.ini
    echo ""
    echo -e "${AMARILLO}Actualizando /etc/frpc.ini...${NC}"

    TMP_FRP=$(mktemp)
    cat > "$TMP_FRP" << EOF
[common]
server_addr = ${HOSTNAME_FRP}
server_port = 7000

[ssh_${PUERTO}]
type = tcp
local_ip = 127.0.0.1
local_port = 22
remote_port = ${PUERTO}
EOF

    ejecutar_sudo cp "$TMP_FRP" /etc/frpc.ini
    rm -f "$TMP_FRP"

    if [ $? -eq 0 ]; then
        echo -e "${VERDE}✓ /etc/frpc.ini actualizado.${NC}"
    else
        echo -e "${ROJO}✗ Error al actualizar /etc/frpc.ini${NC}"
        read -p "Presione Enter..."
        return
    fi

    # Registrar en Notion
    echo ""
    echo -e "${AMARILLO}Registrando en Notion...${NC}"

    RESULTADO=$("$SCRIPT_DIR/notion_hosts.py" add-row \
        --alias "$NOMBRE" \
        --usuario "$USUARIO" \
        --hostname "$HOSTNAME_FRP" \
        --puerto "$PUERTO" 2>&1)

    if [ $? -eq 0 ]; then
        echo -e "${VERDE}✓ $RESULTADO${NC}"
    else
        echo -e "${ROJO}✗ Error al registrar en Notion: $RESULTADO${NC}"
        read -p "Presione Enter..."
        return
    fi

    # Reiniciar servicio frpc
    echo ""
    echo -e "${AMARILLO}Reiniciando servicio frpc...${NC}"
    ejecutar_sudo systemctl restart frpc 2>/dev/null

    if [ $? -eq 0 ]; then
        echo -e "${VERDE}✓ Servicio frpc reiniciado.${NC}"
    else
        echo -e "${AMARILLO}⚠ No se pudo reiniciar frpc (puede que no esté como servicio).${NC}"
    fi

    echo ""
    echo -e "${VERDE}════════════════════════════════════════════════════${NC}"
    echo -e "${VERDE}Configuración completada. Ahora puedes conectarte con:${NC}"
    echo -e "${AZUL}  ssh -p ${PUERTO} ${USUARIO}@${HOSTNAME_FRP}${NC}"
    echo -e "${VERDE}════════════════════════════════════════════════════${NC}"
    echo ""
    read -p "Presione Enter..."
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
