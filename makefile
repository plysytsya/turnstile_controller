.PHONY: install-qr uninstall-qr install-cronjob watch-cronjob trigger-cronjob list-services

# Instalar el script QR como un servicio
install-qr:
	sudo cp /home/manager/turnstile_controller/qr_script.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable qr_script
	sudo systemctl start qr_script
	sudo systemctl status qr_script

# Desinstalar el servicio QR
uninstall-qr:
	sudo systemctl stop qr_script
	sudo systemctl disable qr_script
	sudo rm /etc/systemd/system/qr_script.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

restart-qr:
	sudo systemctl restart qr_script.service

# Instalar el cronjob para descargar la base de datos del cliente
install-cronjob:
	sudo cp /home/manager/turnstile_controller/download_customer_db.service /etc/systemd/system/
	sudo cp /home/manager/turnstile_controller/download_customer_db.timer /etc/systemd/system/
	sudo systemctl daemon-reload  # Reload systemd manager configuration
	sudo systemctl enable download_customer_db.service
	sudo systemctl enable download_customer_db.timer
	sudo systemctl start download_customer_db.timer

# Desinstalar el cronjob de descarga de la base de datos del cliente
uninstall-cronjob:
	sudo systemctl stop download_customer_db.timer
	sudo systemctl disable download_customer_db.service
	sudo systemctl disable download_customer_db.timer
	sudo rm /etc/systemd/system/download_customer_db.service
	sudo rm /etc/systemd/system/download_customer_db.timer
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

# Observar el registro del cronjob en tiempo real
watch-cronjob:
	journalctl -u download_customer_db.service -f

# Verificar el estado del cronjob
status-cronjob:
	sudo systemctl status download_customer_db.timer

# Disparar el cronjob manualmente
trigger-cronjob:
	sudo systemctl start download_customer_db.service

# Listar todos los servicios
list-services:
	systemctl list-units --type=service

# Observar el registro del script QR en tiempo real
logs-qr:
	journalctl -u qr_script -f

logs-cronjob:
	journalctl -u download_customer_db.service -f

venv:
	@source ~/turnstile_controller/venv/bin/activate
