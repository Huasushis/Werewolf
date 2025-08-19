let isOwner = false;
let attendedPlayers = 0;
let started = false;
let canChat = true; // 新增变量，用于控制是否可以发言
let canWolfChat = false;
let isWitchChoosing = false; // 标志变量，用于跟踪女巫的选择状态
let isChoosing = false;
let currentAction = false; // 当前选择的动作（救或毒）
let canToxic = true;
let canPill = true;
var selectPlayer;

$(document).ready(function() {
    function updateGameState(flag) {
        $.ajax({
            url: '/get_game_state',
            method: 'GET',
            success: function(response) {
                if (response.success) {
                    // 更新角色数量显示
                    $('#role-wolf').text(response.roles.wolf);
                    $('#role-seer').text(response.roles.seer);
                    $('#role-witch').text(response.roles.witch);
                    $('#role-hunter').text(response.roles.hunter);
                    $('#role-knight').text(response.roles.knight);
                    $('#role-villager').text(response.roles.villager);

                    // 更新聊天记录
                    if (flag) {
                        const chatMessages = $('#chat-messages');
                        chatMessages.empty();
                        response.chat.forEach(message => {
                            chatMessages.append('<div><strong>' + message.username + ':</strong> ' + message.message + '</div>');
                        });
                    }

                    // 更新狼人聊天记录
                    if (flag) {
                        const wolfChatMessages = $('#wolf-chat-messages');
                        wolfChatMessages.empty();
                        response.wolfchat.forEach(message => {
                            wolfChatMessages.append('<div><strong>' + message.username + ':</strong> ' + message.message + '</div>');
                        });
                    }
                    // scrollToBottomIfAtBottom(wolfChatMessages); // 初始加载时滚动到底部

                    //更新毒药和解药
                    canPill = response.self.pill;
                    canToxic = response.self.toxic;

                    // 更新玩家列表
                    isChoosing = response.self.choice;
                    const playerList = $('#player-list');
                    playerList.empty();
                    started = response.started;
                    Object.keys(response.players).forEach(player => {
                        if (isChoosing && response.players[player].role) {
                            playerList.append(`<button class="btn btn-primary w-100" onclick="selectPlayer('${player}')">` + player + (response.players[player].role ? ' (' + response.players[player].role + ')' : '') + (response.players[player].died ? ' (已死亡)' : '') + `</button>`);
                        } else {
                            // playerList.append('<li class="list-group-item" id="player-' + player + '">' + player + (response.players[player].role ? ' (' + response.players[player].role + ')' : '') + (response.players[player].died ? ' (已死亡)' : '') + '</li>');
                            const listItem = $('<li>').addClass('list-group-item d-flex justify-content-between align-items-center').attr('id', 'player-' + player);
                            listItem.append(player + (response.players[player].role ? ' (' + response.players[player].role + ')' : '') + 
                                (response.players[player].died ? ' (已死亡)' : ''));
                            
                            if (isOwner && !started) {
                                // addClass('kick-button')
                                const kickButton = $('<span>').addClass('kick-button').attr('data-player', player);
                                kickButton.html('<i class="fas fa-times-circle" style="color:red;"></i>');
                                listItem.append(kickButton);
                            }

                            playerList.append(listItem);
                        }
                    });

                    // 更新玩家数量
                    attendedPlayers = response.attendedPlayers;

                    // 更新是否可以发言
                    canChat = response.self.chat;
                    $('#message-input').prop('disabled', !canChat);
                    $('#send-message-btn').prop('disabled', !canChat);
                    canWolfChat = response.self.wolfchat;
                    $('#wolf-message-input').prop('disabled', !canWolfChat);
                    $('#send-wolf-message-btn').prop('disabled', !canWolfChat);

                    // 更新游戏状态
                    const radioButtons = document.querySelectorAll('input[name="role"]');
                    if (response.started) {
                        radioButtons.forEach(button => {
                            button.disabled = true;
                        });
                        $('#role-configuration').hide();
                        
                        // 根据角色显示或隐藏狼人对话窗
                        if (response.self.role !== 'wolf' && response.self.role) {
                            $('#wolf-chat-container').hide();
                        } else {
                            $('#wolf-chat-container').show();
                        }
                    } else {
                        radioButtons.forEach(button => {
                            button.disabled = false;
                        });
                        $('#wolf-chat-container').show();
                        if (isOwner) {
                            $('#role-configuration').show();
                            updateRoleConfiguration(attendedPlayers);
                        } 
                        $('#abstain-button').hide();
                    }

                    $('.add-ai-button').toggle(!started && isOwner);

                    // 更新玩家列表的“+”按钮点击事件
                    $('.add-ai-button').off('click').on('click', function() {
                        websocket.send(JSON.stringify({ type: 'addai' }));
                    });

                    // 绑定踢出按钮的点击事件
                    $('.kick-button').off('click').on('click', function() {
                        const player = String($(this).data('player'));
                        websocket.send(JSON.stringify({ type: 'kick', username: player }));
                    });
                }
            },
            error: function(error) {
                console.error('Error fetching game state:', error.responseText);
            }
        });
    }

    // Send Message Form Submission
    $('#send-message-form').on('submit', function(e) {
        e.preventDefault();
        const message = $('#message-input').val();

        if (message.length > 512) {
            showNotification("你的字符串太长了！");
            return;
        }

        if (message.trim()) {
            websocket.send(JSON.stringify({ type: 'message', content: message }));
            $('#message-input').val('');
        }
        
        if (started) {
            canChat = false;
            $('#message-input').prop('disabled', !canChat);
            $('#send-message-btn').prop('disabled', !canChat);
        }
    });

    // 处理狼人消息发送
    $('#send-wolf-message-form').on('submit', function(event) {
        event.preventDefault();
        const message = $('#wolf-message-input').val();

        if (message.length > 512) {
            showNotification("你的字符串太长了！");
            return;
        }
        if (message.trim()) {
            websocket.send(JSON.stringify({ type: 'wolfmessage', content: message }));
            $('#wolf-message-input').val('');
        }
    });

    // Initial game state update
    updateGameState(true);

    function wrapper() {
        updateGameState(false);
    }
    // Periodically update game state
    setInterval(wrapper, 2500);

    // WebSocket connection
    const websocket = new WebSocket(`ws://${location.host}/ws/${roomCode}`);

    websocket.onopen = function() {
        console.log('Connected to WebSocket');
    };

    websocket.onmessage = function(event) {
        const message = JSON.parse(event.data);
        console.log(message);
        if (message.type === 'message') {
            const chatMessages = $('#chat-messages');
            const atBottom = chatMessages.scrollTop() + chatMessages.innerHeight() + 10 >= chatMessages[0].scrollHeight;
            chatMessages.append('<div><strong>' + message.username + ':</strong> ' + message.message + '</div>');
            if (atBottom) {
                scrollToBottomIfAtBottom(chatMessages); //自动滚动到底部
            }
        } else if (message.type == 'wolfmessage') {
            const chatMessages = $('#wolf-chat-messages');
            const atBottom = chatMessages.scrollTop() + chatMessages.innerHeight() + 10 >= chatMessages[0].scrollHeight;
            chatMessages.append('<div><strong>' + message.username + ':</strong> ' + message.message + '</div>');
            console.log(chatMessages.scrollTop() + chatMessages.innerHeight());
            console.log(chatMessages[0].scrollHeight);
            if (atBottom) {
                scrollToBottomIfAtBottom(chatMessages); //自动滚动到底部
            }
        } else if (message.type === 'leave') {
            const playerList = $('#player-list');
            const playerItem = playerList.find(`:contains("${message.username}")`);
            playerItem.remove();
            showNotification(`${message.username} 离开了房间`);
        } else if (message.type === 'attend') {
            showNotification(`${message.username} 加入了房间`);
        } else if (message.type === 'owner_change') {
            isOwner = true;
            if (isOwner && !started) {
                $('#role-configuration').show();
            } else {
                $('#role-configuration').hide();
            }
            showNotification(`你已经成为新的房主`);
        } else if (message.type === 'notice') {
            showNotification(message.message);
        } else if (message.type === 'choice') {
            handleChoiceMessage(message);
        } else if (message.type == 'started') {
            started = true;
        } else if (message.type == 'ended') {
            started = false;
            // updateGameState(true);
        }
    };

     function handleChoiceMessage(message) {
        if (message.operation === 'witch') {
            // 显示女巫的选择界面
            if (canToxic && canPill) {
                const choiceContainer = $('<div>').addClass('alert alert-warning').text(message.message + ' 请选择：');
                const saveButton = $('<button>').addClass('btn btn-success').text('救').click(() => setWitchAction(false));
                const poisonButton = $('<button>').addClass('btn btn-danger').text('毒').click(() => setWitchAction(true));
                choiceContainer.append(saveButton, ' ', poisonButton);
                $('#notification-container').prepend(choiceContainer);
            } else if (canToxic) {
                showNotification(message.message + "现在请选择你要毒谁？");
                currentAction = true;
            } else if (canPill) {
                showNotification(message.message + "现在请选择你要救谁？");
                currentAction = false;
            } else {
                return;
            }

            isWitchChoosing = true; // 设置女巫选择状态
        } else {
            showNotification(message.message)
        }
        $('#abstain-button').show(); // 显示弃权按钮
        // 将玩家列表变成按钮可选
        isChoosing = true;
        // const playerList = $('#player-list');
        // playerList.find('.list-group-item').each(function() {
        //     const player = $(this).text().split(' ')[0];
        //     const originalText = $(this).text();
        //     $(this).html(`<button class="btn btn-primary w-100" onclick="selectPlayer('${player}')">${originalText}</button>`);
        // });

    }

    function setWitchAction(action) {
        currentAction = action;
        $('#notification-container').children('.alert').remove(); // 移除选择界面
        if (action) {
            canToxic = false;
        } else canPill = false;
        showNotification(`你选择了${action ? '毒' : '救'}`);
    }

    function selectPlayer(username) {
        if (!isChoosing) return;
        if (isWitchChoosing) {
            sendChoice(currentAction, username);
        } else {
            sendChoice(false, username);
        }
    }
    window.selectPlayer = selectPlayer;

    function sendChoice(action, username) {
        if (!isChoosing) return;
        // 还原玩家列表
        $('#abstain-button').hide();
        const playerList = $('#player-list');
        playerList.find('.list-group-item').each(function() {
            const player = $(this).text().split(' ')[0];
            const originalText = $(this).text();
            $(this).html('<li class="list-group-item" id="player-' + player + '">' + originalText + '</li>');
        });
        websocket.send(JSON.stringify({ type: 'choice', action: action, username: username }));
        isChoosing = false;
        isWitchChoosing = false; // 重置女巫选择状态
    }

    function scrollToBottomIfAtBottom(element) {
        element.scrollTop(element[0].scrollHeight);
    }
    
    websocket.onclose = function(e) {
        console.log('Disconnected from WebSocket');
        console.log(e.code + ' ' + e.reason + ' ' + e.wasClean);
        console.log(e);
        showNotification('您已断连...');
        location.reload();
    };

    websocket.onerror = function(error) {
        console.error('WebSocket error:', error);
    };

    window.addEventListener('beforeunload', function(event) {
        $.ajax({
            url: '/leave_room',
            method: 'GET',
            async: false,
            success: function(response) {
                console.log(response);
            }
        });
    });

    function showNotification(message) {
        const notification = $('<div>').addClass('notification').text(message);
        $('#notification-container').prepend(notification);

        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    // Check if user is the owner
    $.ajax({
        url: '/is_owner',
        method: 'GET',
        success: function(response) {
            isOwner = response.is_owner;
            if (isOwner) {
                $('#role-configuration').show();
            }
        },
        error: function(error) {
            console.error('Error checking if user is owner:', error.responseText);
        }
    });

    // Set role on radio button change
    $('input[name="role"]').on('change', function() {
        const role = $(this).val();
        $.ajax({
            url: '/set_role',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ role: role }),
            success: function(response) {
                if (response.success) {
                    showNotification('角色设置成功');
                } else {
                    showNotification('角色设置失败: ' + response.message);
                }
            },
            error: function(error) {
                showNotification('角色设置时出错: ' + error.responseText);
            }
        });
    });

    // Update role configuration
    function updateRoleConfiguration(totalPlayers) {
        const roles = {
            wolf: parseInt($('#wolf').val()),
            seer: parseInt($('#seer').val()),
            witch: parseInt($('#witch').val()),
            hunter: parseInt($('#hunter').val()),
            knight: parseInt($('#knight').val()),
            villager: parseInt($('#villager').val())
        };

        const remaining = totalPlayers - Object.values(roles).reduce((a, b) => a + b, 0);
        $('#remaining').val(remaining);

        if (remaining <= 0) {
            $('#remaining').addClass('negative');
        } else {
            $('#remaining').removeClass('negative');
        }

        if (remaining < 0) {
            showNotification('角色数量超过总人数');
        }
    }

    // Role input change
    $('.form-control').on('change', function() {
        updateRoleConfiguration(attendedPlayers);
    });

    // Start game
    $('#start-game').on('click', function() {
        const roles = {
            wolf: parseInt($('#wolf').val()),
            seer: parseInt($('#seer').val()),
            witch: parseInt($('#witch').val()),
            hunter: parseInt($('#hunter').val()),
            knight: parseInt($('#knight').val()),
            villager: parseInt($('#villager').val())
        };

        const remaining = parseInt($('#remaining').val());
        if (remaining != 0 || roles.wolf < 0 || roles.seer < 0 || roles.witch < 0 || roles.hunter < 0 || roles.knight < 0 || roles.villager < 0) {
            showNotification('分配不正确！');
            return;
        }

        $.ajax({
            url: '/start_game',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ roles: roles }),
            success: function(response) {
                if (response.success) {
                    showNotification('游戏已开始');
                } else {
                    showNotification('游戏开始失败: ' + response.message);
                }
            },
            error: function(error) {
                showNotification('游戏开始时出错: ' + error.responseText);
            }
        });
    });

    $('#wolf-chat-container').removeClass('hidden');
    $('#toggle-wolf-chat-btn').removeClass('hidden');
    $('#toggle-wolf-chat-btn').click(function () {
        $('#wolf-chat-container').toggleClass('hidden');
        $('#toggle-wolf-chat-btn').toggleClass('hidden');
    });

    setInterval(() => {
        websocket.send(JSON.stringify({ type: 'heartbeat' }));
        console.log('Heartbeat sent');
    }, 50000);
});