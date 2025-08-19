// static/js/script.js

$(document).ready(function() {
    // 从 rules.txt 文件中读取规则内容
    $.get('/static/rules.txt', function(data) {
        $('#rules-content').html('<pre>' + data + '</pre>');
    });

    // 创建房间表单提交处理
    $('#create-room-form').on('submit', function(e) {
        e.preventDefault();
        const roomCode = $('#room-code').val();
        const password = $('#password').val();
        const username = $('#username').val();

        $.ajax({
            url: '/create_room',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ room_code: roomCode, password: password, username: username }),
            success: function(response) {
                if (response.success) {
                    window.location.href = '/room/' + response.room_code;
                } else {
                    alert(response.message);
                }
            },
            error: function(error) {
                alert('创建房间时出错: ' + error.responseText);
            }
        });
    });

    // 加入房间表单提交处理
    $('#join-room-form').on('submit', function(e) {
        e.preventDefault();
        const roomCode = $('#room-code-join').val();
        const password = $('#password-join').val();
        const username = $('#username-join').val();

        $.ajax({
            url: '/join_room',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ room_code: roomCode, password: password, username: username }),
            success: function(response) {
                if (response.success) {
                    window.location.href = '/room/' + roomCode;
                } else {
                    alert(response.message);
                }
            },
            error: function(error) {
                alert('加入房间时出错: ' + error.responseText);
            }
        });
    });
});