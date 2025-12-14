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
    echo -e "${AZUL}══════════════ CONFIGURAR CONTROL DE ACCESO (.env) ══════════════${NC}"
    echo ""

    ENV_FILE="/home/manager/turnstile_controller/.env"

    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${ROJO}Error: No existe $ENV_FILE${NC}"
        read -p "Presione Enter..."
        return
    fi

    # Leer valores actuales (sin romper si faltan)
    CUR_ENTRANCE_UUID_A=$(grep -E '^ENTRANCE_UUID_A=' "$ENV_FILE" | head -n1 | cut -d= -f2-)
    CUR_USERNAME=$(grep -E '^USERNAME=' "$ENV_FILE" | head -n1 | cut -d= -f2-)
    CUR_PASSWORD=$(grep -E '^PASSWORD=' "$ENV_FILE" | head -n1 | cut -d= -f2-)
    CUR_HAS_CAMERA=$(grep -E '^HAS_CAMERA=' "$ENV_FILE" | head -n1 | cut -d= -f2-)

    # Normalizar HAS_CAMERA a Python bool si viene en otros formatos
    case "$CUR_HAS_CAMERA" in
        True|False) : ;;
        true|TRUE|1|yes|YES|y|Y|si|SI|s|S) CUR_HAS_CAMERA="True" ;;
        false|FALSE|0|no|NO|n|N|"") CUR_HAS_CAMERA="False" ;;
        *) CUR_HAS_CAMERA="False" ;;
    esac

    echo -e "${VERDE}Valores actuales:${NC}"
    echo "────────────────────────────────────────────────────"
    echo "  ENTRANCE_UUID_A = ${CUR_ENTRANCE_UUID_A}"
    echo "  USERNAME        = ${CUR_USERNAME}"
    echo "  PASSWORD        = (oculto)"
    echo "  HAS_CAMERA      = ${CUR_HAS_CAMERA}"
    echo "────────────────────────────────────────────────────"
    echo ""

    # Pedir nuevos valores (Enter = mantener)
    echo -e "${AMARILLO}ENTRANCE_UUID_A [Enter para mantener]:${NC}"
    read NEW_ENTRANCE_UUID_A

    echo -e "${AMARILLO}USERNAME [Enter para mantener]:${NC}"
    read NEW_USERNAME

    echo -e "${AMARILLO}PASSWORD [Enter para mantener]:${NC}"
    read -s NEW_PASSWORD
    echo ""

    # s/n -> True/False
    if [[ "$CUR_HAS_CAMERA" == "True" ]]; then
        CUR_HAS_CAMERA_HUMAN="s"
    else
        CUR_HAS_CAMERA_HUMAN="n"
    fi

    echo -e "${AMARILLO}¿Tiene cámara? (s/n) [${CUR_HAS_CAMERA_HUMAN}] (Enter para mantener):${NC}"
    read NEW_HAS_CAMERA

    # Aplicar "mantener" si viene vacío
    FINAL_ENTRANCE_UUID_A="${NEW_ENTRANCE_UUID_A:-$CUR_ENTRANCE_UUID_A}"
    FINAL_USERNAME="${NEW_USERNAME:-$CUR_USERNAME}"
    FINAL_PASSWORD="${NEW_PASSWORD:-$CUR_PASSWORD}"

    # HAS_CAMERA: Enter mantiene, s/n convierte
    if [ -z "$NEW_HAS_CAMERA" ]; then
        FINAL_HAS_CAMERA="$CUR_HAS_CAMERA"
    else
        case "$NEW_HAS_CAMERA" in
            s|S) FINAL_HAS_CAMERA="True" ;;
            n|N) FINAL_HAS_CAMERA="False" ;;
            *)
                echo -e "${ROJO}Error: use 's' o 'n'.${NC}"
                read -p "Presione Enter..."
                return
                ;;
        esac
    fi

    # Default absoluto si sigue vacío
    if [ -z "$FINAL_HAS_CAMERA" ]; then
        FINAL_HAS_CAMERA="False"
    fi

    echo ""
    echo -e "${VERDE}Resumen de cambios:${NC}"
    echo "────────────────────────────────────────────────────"
    echo "  ENTRANCE_UUID_A = ${FINAL_ENTRANCE_UUID_A}"
    echo "  USERNAME        = ${FINAL_USERNAME}"
    echo "  PASSWORD        = (oculto)"
    echo "  HAS_CAMERA      = ${FINAL_HAS_CAMERA}"
    echo "────────────────────────────────────────────────────"
    echo ""
    echo -e "${AMARILLO}¿Guardar en $ENV_FILE? (s/n):${NC}"
    read CONFIRMAR

    if [[ ! "$CONFIRMAR" =~ ^[sS]$ ]]; then
        echo -e "${AMARILLO}Cancelado. No se guardó nada.${NC}"
        read -p "Presione Enter..."
        return
    fi

    # Función interna: setear o agregar KEY=VALUE, sin tocar otras líneas
    _set_or_append_env_kv() {
        local key="$1"
        local value="$2"
        local file="$3"

        local esc
        esc=$(printf '%s' "$value" | sed -e 's/[\/&\\]/\\&/g')

        if grep -qE "^${key}=" "$file"; then
            sed -i "0,/^${key}=.*/s//${key}=${esc}/" "$file"
        else
            printf '\n%s=%s\n' "$key" "$value" >> "$file"
        fi
    }

    # Backup antes de editar
    TS=$(date +%Y%m%d-%H%M%S)
    ejecutar_sudo cp "$ENV_FILE" "${ENV_FILE}.bak.${TS}" || {
        echo -e "${ROJO}Error creando backup.${NC}"
        read -p "Presione Enter..."
        return
    }

    # Editar usando tmp
    TMP_ENV=$(mktemp)
    ejecutar_sudo cp "$ENV_FILE" "$TMP_ENV" || {
        echo -e "${ROJO}Error copiando .env a tmp.${NC}"
        rm -f "$TMP_ENV"
        read -p "Presione Enter..."
        return
    }

    _set_or_append_env_kv "ENTRANCE_UUID_A" "$FINAL_ENTRANCE_UUID_A" "$TMP_ENV"
    _set_or_append_env_kv "USERNAME" "$FINAL_USERNAME" "$TMP_ENV"
    _set_or_append_env_kv "PASSWORD" "$FINAL_PASSWORD" "$TMP_ENV"
    _set_or_append_env_kv "HAS_CAMERA" "$FINAL_HAS_CAMERA" "$TMP_ENV"

    ejecutar_sudo cp "$TMP_ENV" "$ENV_FILE"
    rm -f "$TMP_ENV"

    echo -e "${VERDE}✓ .env actualizado correctamente.${NC}"
    echo ""
    echo -e "${AMARILLO}(Reinicie el sistema para que los cambios sean efectivos)${NC}"
    echo ""

    read -p "Presione Enter..."
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
