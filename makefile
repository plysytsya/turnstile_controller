.PHONY: install-qr uninstall-qr install-cronjob watch-cronjob trigger-cronjob list-services

install-qr:
	sudo cp /home/manager/turnstile_controller/qr_script.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable qr_script
	sudo systemctl start qr_script
	sudo systemctl status qr_script

uninstall-qr:
	sudo systemctl stop qr_script
	sudo systemctl disable qr_script
	sudo rm /etc/systemd/system/qr_script.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

install-cronjob:
	sudo cp /home/manager/turnstile_controller/download_customer_db.service /etc/systemd/system/
	sudo cp /home/manager/turnstile_controller/download_customer_db.timer /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable download_customer_db.service
	sudo systemctl enable download_customer_db.timer
	sudo systemctl start download_customer_db.timer

uninstall-cronjob:
	sudo systemctl stop download_customer_db.timer
	sudo systemctl disable download_customer_db.service
	sudo systemctl disable download_customer_db.timer
	sudo rm /etc/systemd/system/download_customer_db.service
	sudo rm /etc/systemd/system/download_customer_db.timer
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

watch-cronjob:
	journalctl -u download_customer_db.service -f

status-cronjob:
	sudo systemctl status download_customer_db.timer

trigger-cronjob:
	sudo systemctl start download_customer_db.service

list-services:
	systemctl list-units --type=service

logs-qr:
	journalctl -u qr_script -f

logs-cronjob:
	journalctl -u download_customer_db.service -f
