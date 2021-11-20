﻿namespace ChattingRoom.Core.Messages;

[Msg("UserInfo", Direction.ClientToServer, Direction.ServerToClient)]
public class UserInfoMsg : IMessage
{
#nullable disable
    public string Account
    {
        get; set;
    }
#nullable enable
    public string? NickName
    {
        get; set;
    }
    public void Deserialize(dynamic json)
    {
        Account = json.Account;
        NickName = json.NickName;
    }

    public void Serialize(dynamic json)
    {
        json.Account = Account;
        if (NickName is not null)
        {
            json.NickName = NickName;
        }
    }
}

[Msg("ChangePassword", Direction.ClientToServer)]
public class ChangePasswordMsg : IMessage
{
    public void Deserialize(dynamic json)
    {

    }

    public void Serialize(dynamic json)
    {

    }
}

[Msg("ChangePasswordResult", Direction.ServerToClient)]
public class ChangePasswordResultMsg : IMessage
{
    public bool OK
    {
        get; set;
    } = false;

    public void Deserialize(dynamic json)
    {
        OK = json.OK;
    }

    public void Serialize(dynamic json)
    {
        json.OK = OK;
    }
}
