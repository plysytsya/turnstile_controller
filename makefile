.PHONY: \
	install-qr-a \
	uninstall-qr-a \
	restart-qr-a \
	logs-qr-a \
	install-qr-b \
	uninstall-qr-b \
	restart-qr-b \
	logs-qr-b \
	install-heartbeat uninstall-heartbeat restart-heartbeat logs-heartbeat \
	install-cronjob uninstall-cronjob watch-cronjob status-cronjob trigger-cronjob list-services \
	venv \
	install-upload uninstall-upload restart-upload logs-upload \
	install-videorecorder uninstall-videorecorder restart-videorecorder logs-videorecorder \
	restart-frp logs-frp install-frp \
	install-mqtt-sender \
	uninstall-mqtt-sender \
	restart-mqtt-sender \
	logs-mqtt-sender \
	install-mqtt-receiver \
	uninstall-mqtt-receiver \
	restart-mqtt-receiver \
	logs-mqtt-receiver

############################
# QR Script A Targets
# (Installation & configuration using qr_script_a.service)
############################

install-qr-a:
	sudo cp /home/manager/turnstile_controller/qr_script_a.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable qr_script_a
	sudo systemctl start qr_script_a
	sudo systemctl status qr_script_a

uninstall-qr-a:
	sudo systemctl stop qr_script_a
	sudo systemctl disable qr_script_a
	sudo rm /etc/systemd/system/qr_script_a.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

restart-qr-a:
	sudo systemctl restart qr_script_a.service

logs-qr-a:
	journalctl -u qr_script_a -f

############################
# QR Script B Targets
# (Runtime management using qr_script_b.service)
############################

install-qr-b:
	sudo cp /home/manager/turnstile_controller/qr_script_b.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable qr_script_b
	sudo systemctl start qr_script_b
	sudo systemctl status qr_script_b

uninstall-qr-b:
	sudo systemctl stop qr_script_b
	sudo systemctl disable qr_script_b
	sudo rm /etc/systemd/system/qr_script_b.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

restart-qr-b:
	sudo systemctl restart qr_script_b.service

logs-qr-b:
	journalctl -u qr_script_b -f

############################
# Heartbeat Monitor Targets
############################

install-heartbeat:
	sudo cp /home/manager/turnstile_controller/heartbeat-monitor.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable heartbeat-monitor
	sudo systemctl start heartbeat-monitor
	sudo systemctl status heartbeat-monitor

uninstall-heartbeat:
	sudo systemctl stop heartbeat-monitor
	sudo systemctl disable heartbeat-monitor
	sudo rm /etc/systemd/system/heartbeat-monitor.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

restart-heartbeat:
	sudo systemctl restart heartbeat-monitor.service

logs-heartbeat:
	journalctl -u heartbeat-monitor -f

############################
# Cronjob Targets (Download Customer DB)
############################

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

############################
# Service Listing & Virtual Environment
############################

list-services:
	systemctl list-units --type=service

venv:
	@source ~/turnstile_controller/venv/bin/activate

############################
# Upload Service Targets
############################

install-upload:
	sudo cp /home/manager/turnstile_controller/upload.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable upload
	sudo systemctl start upload
	sudo systemctl status upload

uninstall-upload:
	sudo systemctl stop upload
	sudo systemctl disable upload
	sudo rm /etc/systemd/system/upload.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

restart-upload:
	sudo systemctl restart upload.service

logs-upload:
	journalctl -u upload -f

############################
# Videorecorder Service Targets
############################

install-videorecorder:
	sudo cp /home/manager/turnstile_controller/videorecorder.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable videorecorder
	sudo systemctl start videorecorder
	sudo systemctl status videorecorder

uninstall-videorecorder:
	sudo systemctl stop videorecorder
	sudo systemctl disable videorecorder
	sudo rm /etc/systemd/system/videorecorder.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

restart-videorecorder:
	sudo systemctl restart videorecorder.service

logs-videorecorder:
	journalctl -u videorecorder -f

############################
# FRP Service Targets
############################

restart-frp:
	sudo systemctl daemon-reload
	sudo systemctl restart frpc.service
	sudo systemctl status frpc.service

logs-frp:
	sudo journalctl -u frpc.service -f

install-frp:
	sudo systemctl enable /etc/systemd/system/frpc.service
	sudo systemctl start frpc.service

############################
# Bluetooth Sender Service Targets
############################

install-mqtt-sender:
	sudo cp /home/manager/turnstile_controller/mqtt-sender.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable mqtt-sender
	sudo systemctl start mqtt-sender
	sudo systemctl status mqtt-sender

uninstall-mqtt-sender:
	sudo systemctl stop mqtt-sender
	sudo systemctl disable mqtt-sender
	sudo rm /etc/systemd/system/mqtt-sender.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

restart-mqtt-sender:
	sudo systemctl restart mqtt-sender.service

logs-mqtt-sender:
	journalctl -u mqtt-sender -f

############################

install-mqtt-receiver:
	sudo cp /home/manager/turnstile_controller/mqtt-receiver.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable mqtt-receiver
	sudo systemctl start mqtt-receiver
	sudo systemctl status mqtt-receiver

uninstall-mqtt-receiver:
	sudo systemctl stop mqtt-receiver
	sudo systemctl disable mqtt-receiver
	sudo rm /etc/systemd/system/mqtt-receiver.service
	sudo systemctl daemon-reload
	sudo systemctl reset-failed

restart-mqtt-receiver:
	sudo systemctl restart mqtt-receiver.service

logs-mqtt-receiver:
	journalctl -u mqtt-receiver -f